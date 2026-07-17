# server.py
import os
import sys
import json
import httpx
import logging
import sqlite3
import aiosqlite
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

# Explicitly import all modern Qdrant client components
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastapi.middleware.cors import CORSMiddleware

# =============================================================
# 1. PERMANENT LOGGING OVERHAUL
# =============================================================
logger = logging.getLogger("rag_app")
logger.setLevel(logging.INFO)

# Prevent duplicate handlers if the server reloads during execution
if not logger.handlers:
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    # File handler for standard runtime details
    file_handler = logging.FileHandler("app.log", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # File handler for tracking system bugs and exceptions
    error_handler = logging.FileHandler("error.log", encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    # Terminal stream handler so you see logs live in the console
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    logger.addHandler(stream_handler)

# Disable corporate SSL bundle flags for local network ease
os.environ["HTTPX_VERIFY"] = "False" 

OLLAMA_URL = "http://127.0.0.1:11434/v1/chat/completions"
DB_FILE = "chatbot_history.db"

model = None
qdrant_client = None

COLLECTION_NAME = "JAI_HIND_COLLEGE_DATA" 
VECTOR_DIMENSION = 384




#SQLITE HELPER LOGIC FOR CONVERSATION RETRIEVAL
def init_sqlite_db():
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id)")
    
    connection.commit()
    connection.close()
    logger.info("SQLite database and indexing initialized successfully.")

async def insert_message(session_id: str, role: str, content: str):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content)
        )
        await db.commit()    
async def retrieve_messages(session_id: str):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            "SELECT role, content, timestamp FROM messages WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,)
        )
        rows = await cursor.fetchall()
        return [{"role": row[0], "content": row[1], "timestamp": row[2]} for row in rows]        
# =============================================================
# 2. APPLICATION LIFECYCLE (DB STARTUP & TEXT INGESTION)
# =============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting local campus system initialization...")
    global model, qdrant_client
    
    try:
        model = SentenceTransformer('all-MiniLM-L6-v2')
        qdrant_client = AsyncQdrantClient(path="./local_qdrant_storage")

        if not await qdrant_client.collection_exists(COLLECTION_NAME):
            logger.info("Vector database index not detected. Compiling payload from chunks...")
            try:
                with open("jai_hind_chunks.json", "r", encoding="utf-8") as f:
                    chunks_data = json.load(f)
            except FileNotFoundError:
                logger.error("Execution Failure: 'jai_hind_chunks.json' missing from root directory!")
                sys.exit(1)

            await qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=VECTOR_DIMENSION, distance=Distance.COSINE)
            )
            
            points = []
            global_id = 1
            
            for item in chunks_data:
                chunk_content = item.get("content", "").strip()
                page_url = item.get("source_url", "https://www.jaihindcollege.com/")
                source_type = item.get("type", "webpage")
                
                if not chunk_content:
                    continue

                enriched_text = (
                    f"College Name: Jai Hind College (Autonomous), Mumbai\n"
                    f"Source Type: {source_type.upper()}\n"
                    f"Source URL: {page_url}\n"
                    f"Information Detail:\n{chunk_content}"
                )
            
                dense_vector = model.encode(enriched_text).tolist()
                points.append(
                    PointStruct(
                        id=global_id,
                        vector=dense_vector,
                        payload={
                            "text": enriched_text,
                            "source": page_url
                        }
                    )
                )
                global_id += 1
                
            await qdrant_client.upsert(collection_name=COLLECTION_NAME, wait=True, points=points)
            logger.info(f"Local Qdrant index compiled with {global_id - 1} semantic blocks.")
        else:
            logger.info("Local Qdrant vector index loaded from disk storage successfully.")
            
    except Exception as init_err:
        logger.exception("Fatal crash during lifecycle startup initialization: %s", init_err)
        sys.exit(1)
        
    yield
    await qdrant_client.close()
    logger.info("Database connection closed cleanly.")

app = FastAPI(title="Campus RAG API Gateway Service (Ollama Offline Edition)", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================
# 3. SCHEMAS FOR DYNAMIC ROUTING
# =============================================================
class ChatRequest(BaseModel):
    question: str
    selected_model: str
    session_id: str  # Dynamically supplied by the Gradio toggle selector

class ChatResponse(BaseModel):
    answer: str

# =============================================================
# 4. CHAT PROCESSING ENDPOINT WITH ACCURACY CONTROLS
# =============================================================
@app.post("/api/chat", response_model=ChatResponse) 
async def chat_endpoint(request: ChatRequest):
    global model, qdrant_client
    user_query = request.question.strip()
    active_model = request.selected_model
    session_id = request.session_id
    
    if not user_query:
        raise HTTPException(status_code=400, detail="Question field cannot be blank.")
        
    try:
        query_dense = model.encode(user_query).tolist()
        hits = []

        # Multi-version client mapping layer to ensure zero database search exceptions
        try:
            if hasattr(qdrant_client, "query_points"):
                resp = await qdrant_client.query_points(collection_name=COLLECTION_NAME, query=query_dense, limit=6)
                hits = getattr(resp, "points", resp)
            elif hasattr(qdrant_client, "search"):
                hits = await qdrant_client.search(collection_name=COLLECTION_NAME, query_vector=query_dense, limit=6)
            elif hasattr(qdrant_client, "search_points"):
                hits = await qdrant_client.search_points(collection_name=COLLECTION_NAME, query_vector=query_dense, limit=6)
            else:
                logger.error("No compatible search method found on asyncqdrantclient instance.")
                hits = []
        except Exception as db_err:
            logger.error(f"Error while querying Qdrant: {db_err}; proceeding with empty context.")
            hits = []            

        retrieved_chunks = []
        for hit in hits or []:
            payload = None
            if hasattr(hit, "payload"):
                payload = getattr(hit, "payload")
            elif isinstance(hit, dict):
                payload = hit.get("payload")

            if isinstance(payload, dict):
                text_content = payload.get("text")
                if text_content:
                    retrieved_chunks.append(text_content)

        context = "\n\n".join(retrieved_chunks) if retrieved_chunks else "No relevant context found in local records."

        # Metadata extraction specifically for debugging file records
        try:
            retrieved_meta = []
            for hit in hits or []:
                entry = {}
                entry_id = getattr(hit, "id", None) if hasattr(hit, "id") else (hit.get("id") if isinstance(hit, dict) else None)
                entry_score = getattr(hit, "score", None) if hasattr(hit, "score") else (hit.get("score") if isinstance(hit, dict) else None)
                payload = getattr(hit, "payload", None) if hasattr(hit, "payload") else (hit.get("payload") if isinstance(hit, dict) else None)
                entry_text = payload.get("text") if isinstance(payload, dict) else None
                entry["id"] = entry_id
                entry["score"] = entry_score
                entry["text"] = (entry_text[:200] + "...") if isinstance(entry_text, str) and len(entry_text) > 200 else entry_text
                retrieved_meta.append(entry)
            logger.info(f"Using Model: {active_model} | Chunks for query '{user_query}': {json.dumps(retrieved_meta, ensure_ascii=False)}")
        except Exception:
            logger.exception("Failed to log retrieved chunks metadata")                 
                    
        system_instruction = (
            "You are the friendly, knowledgeable official AI ambassador for Jai Hind College (Autonomous), Mumbai.\n"
            "Speak directly as a helpful human guide using a first-person perspective (use 'I', 'me', 'our', 'we').\n\n"
            "CRITICAL PERSONALIZATION RULES:\n"
            "1. Adopt an empathetic, polished, and authentic tone. Never say 'Based on the reference text' or 'According to the portal provided'. Treat the knowledge as your own lived experience working here.\n"
            "2. If a student asks where we are located, reply naturally: 'We are situated right on A Road in Churchgate, South Mumbai! Our campus is incredibly easy to reach since we're just a short walk from the Churchgate railway station.'\n"
            "3. Be concise and structured, using standard bolding or bullet points where relevant.\n"
            "4. If a student asks about something we don't have listed in our data, answer like a true peer: 'I checked our official listings, and we don't have that resource listed on campus right now. I highly recommend checking in with our administrative office directly at (91-22) 22041095 so we can point you in the right direction!'\n\n"
            f"PORTAL CORE RECORDS:\n{context}\n\n"
            "Provide a supportive and accurate resolution."
        )

        # Asynchronous communication link with your local hardware's Ollama runtime service
        async with httpx.AsyncClient(verify=False) as client:
            ollama_payload = {
                "model": active_model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_query}
                ],
                # Temperature and predict boundaries optimized to balance speed and accuracy on consumer CPUs
                "options": {
                    "temperature": 0.15,
                    "num_predict": 250,
                    "presence_penalty": 0.3
                }
            }
            
            response = await client.post(OLLAMA_URL, json=ollama_payload, timeout=60.0)
            
            if response.status_code != 200:
                logger.error(f"Ollama backend returned error code {response.status_code}: {response.text}")
                raise HTTPException(status_code=500, detail="Ollama internal text generation failed.")
                
            completion = response.json()
            bot_response = completion["choices"][0]["message"]["content"]
            
        logger.info(f"Successfully generated first-person reply via local {active_model} engine.")
        return ChatResponse(answer=bot_response)

    except Exception as e:
        logger.exception("Core API Gateway Processing Fault encountered: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)