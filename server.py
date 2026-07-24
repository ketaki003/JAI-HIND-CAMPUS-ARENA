import os
import sys
import json
import uuid
import time
import httpx
import logging
import sqlite3
import aiosqlite
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

# Modern Qdrant client components
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastapi.middleware.cors import CORSMiddleware

# =============================================================
# 1. ENHANCED PRODUCTION LOGGING SETUP
# =============================================================
logger = logging.getLogger("rag_app")
logger.setLevel(logging.INFO)

if not logger.handlers:
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] [Thread-%(thread)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler("app.log", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    error_handler = logging.FileHandler("error.log", encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    logger.addHandler(stream_handler)

os.environ["HTTPX_VERIFY"] = "False" 

OLLAMA_URL = "http://127.0.0.1:11434/v1/chat/completions"
DB_FILE = "chatbot_history.db"

model = None
qdrant_client = None

COLLECTION_NAME = "JAI_HIND_COLLEGE_DATA" 
VECTOR_DIMENSION = 384

# =============================================================
# SQLITE HELPER LOGIC FOR CONVERSATION RETRIEVAL
# =============================================================
def init_sqlite_db():
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            chunk TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_session ON messages(user_id, session_id)")
    connection.commit()
    connection.close()
    logger.info("SQLite multi-user database initialized successfully.")

async def insert_chat_turn(user_id: str, session_id: str, question: str, answer: str, chunk: str = ""):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT INTO messages (user_id, session_id, question, answer, chunk) VALUES (?, ?, ?, ?, ?)",
            (user_id, session_id, question, answer, chunk)
        )
        await db.commit()

async def retrieve_messages(user_id: str, session_id: str, limit: int = 6):
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT question, answer FROM messages WHERE user_id = ? AND session_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, session_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            normalized_history = []
            for r in reversed(rows):
                normalized_history.append({"role": "user", "content": r["question"]})
                normalized_history.append({"role": "assistant", "content": r["answer"]})
            return normalized_history

async def generate_ai_title(first_question: str) -> str:
    if not first_question:
        return "New Conversation"
    
    prompt = (
        f"Summarize the following question into a short, concise 3 to 4 word chat topic title. "
        f"Do NOT use quotes, prefixes, or punctuation. Return ONLY the title.\n\n"
        f"Question: \"{first_question}\""
    )
    
    try:
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.post(
                OLLAMA_URL,
                json={
                    "model": "qwen2.5:0.5b",
                    "messages": [{"role": "user", "content": prompt}],
                    "options": {"temperature": 0.1, "num_predict": 20}
                },
                timeout=5.0
            )
            if resp.status_code == 200:
                res_data = resp.json()
                if "choices" in res_data:
                    title = res_data["choices"][0]["message"]["content"].strip()
                elif "message" in res_data:
                    title = res_data["message"].get("content", "").strip()
                else:
                    title = first_question[:30]
                
                clean_title = title.replace('"', '').replace("'", "").strip()
                return (clean_title[:35] + "...") if len(clean_title) > 35 else clean_title
    except Exception as e:
        logger.warning(f"Could not auto-generate AI title: {e}")
        
    return (first_question[:30] + "...") if len(first_question) > 30 else first_question

async def list_conversation_summaries(user_id: str = "user1"):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            """
            SELECT session_id, MIN(timestamp) AS created_at, MAX(timestamp) AS updated_at
            FROM messages
            WHERE user_id = ?
            GROUP BY session_id
            ORDER BY updated_at DESC
            """,
            (user_id,)
        )
        rows = await cursor.fetchall()

        summaries = []
        for session_id, created_at, updated_at in rows:
            title_cursor = await db.execute(
                "SELECT question FROM messages WHERE session_id = ? AND user_id = ? ORDER BY id ASC LIMIT 1",
                (session_id, user_id),
            )
            title_row = await title_cursor.fetchone()
            if title_row and title_row[0]:
                raw_question = title_row[0].strip()
                clean_title = await generate_ai_title(raw_question)
            else:
                clean_title = f"Chat ({session_id[:8]})"   
 
            summaries.append(
                {
                    "session_id": session_id,
                    "title": clean_title,
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            )
        return summaries

# =============================================================
# 2. APPLICATION LIFECYCLE WITH MARKDOWN-AWARE INDEXING
# =============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting local campus system initialization...")
    global model, qdrant_client
    
    try:
        init_sqlite_db()
        model = SentenceTransformer('all-MiniLM-L6-v2')
        qdrant_client = AsyncQdrantClient(path="./local_qdrant_storage")

        if not await qdrant_client.collection_exists(COLLECTION_NAME):
            logger.info("Vector database index not detected. Compiling payload from markdown chunks...")
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
                page_title = item.get("title", "Jai Hind College")
                page_url = item.get("source_url", "https://www.jaihindcollege.com/")
                source_type = item.get("type", "webpage")
                
                if not chunk_content:
                    continue

                # Structure text for vector embedding naturally with Markdown header
                text_to_embed = f"# {page_title}\n\n{chunk_content}"
                dense_vector = model.encode(text_to_embed).tolist()

                points.append(
                    PointStruct(
                        id=global_id,
                        vector=dense_vector,
                        payload={
                            "text": chunk_content,
                            "title": page_title,
                            "source": page_url,
                            "type": source_type
                        }
                    )
                )
                global_id += 1
                
            await qdrant_client.upsert(collection_name=COLLECTION_NAME, wait=True, points=points)
            logger.info(f"Local Qdrant index compiled with {global_id - 1} markdown blocks.")
        else:
            logger.info("Local Qdrant vector index loaded from disk storage successfully.")
            
    except Exception as init_err:
        logger.exception("Fatal crash during lifecycle startup initialization: %s", init_err)
        sys.exit(1)
        
    yield
    await qdrant_client.close()
    logger.info("Database connection closed cleanly.")

app = FastAPI(title="Campus RAG API Gateway Service", lifespan=lifespan)

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
    session_id: str = "default-session"
    user_id: str = "user1"
    history: list | None = None

class ChatResponse(BaseModel):
    answer: str

# =============================================================
# 4. CHAT ENDPOINT
# =============================================================
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    global model, qdrant_client
    start_time = time.time()
    
    user_query = request.question.strip()
    active_model = request.selected_model 
    session_id = request.session_id or "default-session"
    user_id = request.user_id or "user1"
    
    if not user_query:
        logger.warning(f"[USER: {user_id} | SESSION: {session_id}] Blank query submission rejected.")
        raise HTTPException(status_code=400, detail="Question field cannot be blank.")

    logger.info(f"==================== NEW INCOMING CHAT REQUEST ====================")
    logger.info(f"[REQUEST METADATA] User ID: '{user_id}' | Session ID: '{session_id}' | Model: '{active_model}'")
    logger.info(f"[USER QUERY] Character Length: {len(user_query)} | Content: \"{user_query}\"")

    try:
        history = await retrieve_messages(user_id, session_id, limit=3)
        logger.info(f"[HISTORY] Loaded {len(history)} previous turns from SQLite history.")

        # Vector Search
        retrieval_start = time.time()
        query_dense = model.encode(user_query).tolist()
        hits = []

        try:
            if hasattr(qdrant_client, "query_points"):
                resp = await qdrant_client.query_points(collection_name=COLLECTION_NAME, query=query_dense, limit=3)
                hits = getattr(resp, "points", resp)
            elif hasattr(qdrant_client, "search"):
                hits = await qdrant_client.search(collection_name=COLLECTION_NAME, query_vector=query_dense, limit=3)
            else:
                hits = []
        except Exception as db_err:
            logger.error(f"[QDRANT ERROR] Failure during vector search: {db_err}; proceeding with fallback.")
            hits = []           

        retrieval_latency = round((time.time() - retrieval_start) * 1000, 2)

        # Context Formatting for Markdown Chunks
        formatted_context_list = []
        logger.info(f"[RETRIEVAL] Qdrant search finished in {retrieval_latency}ms. Retrieved {len(hits)} hits.")

        for idx, hit in enumerate(hits or [], start=1):
            payload = getattr(hit, "payload", hit.get("payload") if isinstance(hit, dict) else {})
            score = getattr(hit, "score", "N/A")
            
            if isinstance(payload, dict) and payload.get("text"):
                chunk_text = payload["text"]
                title = payload.get("title", "Campus Information")
                source_url = payload.get("source", "N/A")
                
                # Format each retrieved chunk clearly for the LLM
                formatted_block = f"### Source {idx}: {title}\nURL: {source_url}\n{chunk_text}"
                formatted_context_list.append(formatted_block)

                preview_snippet = chunk_text[:120].replace('\n', ' ') + "..."
                logger.info(
                    f"  ├─ [Chunk #{idx}] Score: {score} | Title: '{title}' | Source: {source_url}"
                )
                logger.info(f"  │  Snippet: \"{preview_snippet}\"")

        context = "\n\n---\n\n".join(formatted_context_list) if formatted_context_list else "No relevant context found in local records."
        total_context_size = sum(len(c) for c in formatted_context_list)
        logger.info(f"[CONTEXT SUMMARY] Total Injected Context Size: {total_context_size} characters across {len(formatted_context_list)} chunks.")

        # Prompt Instructions
        system_instruction = (
            "You are a friendly, warm, and helpful senior student guide at Jai Hind College (Autonomous), Mumbai.\n"
            "Chat naturally like a real human student ambassador. Use first-person language ('I', 'we', 'our campus') "
            "and speak in a conversational, welcoming, and relaxed tone.\n\n"
            "COMMUNICATION STYLE:\n"
            "- Always speak in the first person, as if you are part of the college. (Use: \"I\", \"we\", \"our college\", \"our campus\")\n"
            "- Maintain a friendly, confident, and professional tone.\n"
            "- Keep responses natural and conversational, not robotic.\n"
            "- Do NOT mention sources like (\"provided text\", \"context\", or \"database\").\n\n"
            "PERMANENT CAMPUS FACTS (STRICT GROUND TRUTH):\n"
            "- Address: 'A' Road, Churchgate, Mumbai, Maharashtra - 400020 (near Churchgate Station)\n"
            "- Principal: Prof. (Dr.) Vijay Dabholkar\n"
            "- Contact Phone: (91-22) 22041095 / 22040256\n"
            "- Website: https://www.jaihindcollege.com/\n\n"
            "STRICT RULES:\n"
            "1. FOR MISSING AMENITIES/FACILITIES (e.g., Swimming Pool, Hostel): We DO NOT have an on-campus swimming pool or private hostel buildings.\n"
            "   If asked, reply politely: 'We don't have a swimming pool on our campus, but our sports circle is very active! Feel free to reach out to our office at (91-22) 22041095 for sports details.'\n"
            "2. NEVER generate fake room numbers, unknown departments, or false locations.\n"
            "3. DO NOT hallucinate or guess under any circumstances.\n\n"
            f"VERIFIED CAMPUS INFORMATION:\n{context}"
        )

        ollama_messages = [{"role": "system", "content": system_instruction}]
        for turn in history:
            ollama_messages.append({"role": turn["role"], "content": turn["content"]})
        ollama_messages.append({"role": "user", "content": user_query})

        llm_start = time.time()
        async with httpx.AsyncClient(verify=False) as client:
            ollama_payload = {
                "model": active_model,
                "messages": ollama_messages,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 180,
                    "presence_penalty": 0.1
                }
            }
            
            response = await client.post(OLLAMA_URL, json=ollama_payload, timeout=60.0)
            response_payload = response.json()

            if response.status_code == 200:
                if isinstance(response_payload, dict):
                    if "choices" in response_payload:
                        bot_response = response_payload["choices"][0]["message"]["content"]
                    elif "message" in response_payload:
                        bot_response = response_payload["message"].get("content", "")
                    elif "response" in response_payload:
                        bot_response = response_payload["response"]
                    else:
                        bot_response = "I’m having trouble processing the reply from the model service."
                else:
                    bot_response = "I’m having trouble processing the reply from the model service."
            else:
                bot_response = "I’m having trouble processing information right now."

        llm_latency = round((time.time() - llm_start) * 1000, 2)
        total_request_latency = round((time.time() - start_time) * 1000, 2)

        logger.info(f"[LLM GENERATION] Ollama call finished in {llm_latency}ms.")
        logger.info(f"[RESPONSE METRICS] Generated Answer Size: {len(bot_response)} chars | Total End-to-End Latency: {total_request_latency}ms")
        logger.info(f"[GENERATED ANSWER PREVIEW] \"{bot_response[:150].replace('\n', ' ')}...\"")

        await insert_chat_turn(user_id, session_id, user_query, bot_response, context)
        logger.info(f"[DATABASE] Chat turn successfully recorded into SQLite database.")
        logger.info(f"=================================================================\n")
        
        return ChatResponse(answer=bot_response)

    except Exception as e:
        logger.exception(f"[CRITICAL ERROR] Pipeline crash during query processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/conversations")
async def get_conversations(user_id: str = "user1"):
    summaries = await list_conversation_summaries(user_id=user_id)
    return {"conversations": summaries}

@app.get("/api/conversations/{session_id}")
async def get_conversation(session_id: str, user_id: str = "user1"):
    messages = await retrieve_messages(user_id=user_id, session_id=session_id)
    return {"session_id": session_id, "messages": messages}

@app.post("/api/conversations/new")
async def create_new_conversation():
    new_session_id = f"chat-{uuid.uuid4().hex[:8]}"
    return {"session_id": new_session_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)