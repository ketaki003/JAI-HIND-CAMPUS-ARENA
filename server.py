import os
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import json
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastapi.middleware.cors import CORSMiddleware
from huggingface_hub import InferenceClient 
import logging
# Ensure log directory exists

logger = logging.getLogger("rag_app")
logger.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

# Info log file
file_handler = logging.FileHandler("app.log")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

# Error log file (separate)
error_handler = logging.FileHandler("error.log")
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(formatter)

# Console output
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

# Attach handlers
logger.addHandler(file_handler)
logger.addHandler(error_handler)
logger.addHandler(stream_handler)



#  1. GLOBAL SSL BYPASS FOR CORPORATE LAPTOP
os.environ["CURL_CA_BUNDLE"] = ""  
os.environ["HTTPX_VERIFY"] = "False" 
os.environ["NO_PROXY"] = "huggingface.co,api-inference.huggingface.co"

import requests
requests.packages.urllib3.disable_warnings()
original_requests_init = requests.Session.__init__
def bypass_requests_ssl(self, *args, **kwargs):
    original_requests_init(self, *args, **kwargs)
    self.verify = False
requests.Session.__init__ = bypass_requests_ssl

# -------------------------------------------------------------
#  HUGGING FACE INFERENCE CONFIGURATION
# -------------------------------------------------------------
#  Paste your actual 'hf_...' token key string here:

HF_TOKEN_ = os.getenv("HF_TOKEN")

# Enterprise-grade open-source instruction model hosted on Hugging Face Serverless infrastructure
TARGET_MODEL = "Qwen/Qwen2.5-7B-Instruct"

# -------------------------------------------------------------
# STEP 2: Async Lifespan Storage & Vector DB Matrix Setup
# -------------------------------------------------------------
model = None
qdrant_client = None
hf_client = None

COLLECTION_NAME = "JAI_HIND_COLLEGE_DATA" 
VECTOR_DIMENSION = 384

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting system intialization")

    global model, qdrant_client, hf_client
    
    logger.info(" Initializing Local Embeddings Engine & Storage Vector Space...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    qdrant_client = AsyncQdrantClient(path="./local_qdrant_storage")
    
    logger.info(f" Connecting to Hugging Face Serverless Endpoint: {TARGET_MODEL}...")
    hf_client = InferenceClient(token=HF_TOKEN)

    # Build DB collection matrix if it doesn't exist on local storage disk yet
    if not await qdrant_client.collection_exists(COLLECTION_NAME):
        logger.info(" Database index structure empty. Compiling storage from JSON data...")
        try:
            with open("college_data.json", "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            logger.info(" Critical Execution Failure: 'college_data.json' missing from root directory!")
            sys.exit(1)

        await qdrant_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_DIMENSION, distance=Distance.COSINE)
        )
        
        points = []
        for item in data:
            dense_vector = model.encode(item["text"]).tolist()
            points.append(
                PointStruct(
                    id=item["id"],
                    vector=dense_vector,
                    payload={"text": item["text"], "source": item.get("source", "Campus Portal Scraper")}
                )
            )
        
        await qdrant_client.upsert(collection_name=COLLECTION_NAME, wait=True, points=points)
        logger.info(" Local Qdrant single-vector index successfully built from JSON data.")
    else:
        logger.info(" Local Qdrant vector index verified and successfully loaded from local storage storage.")
        
    yield
    await qdrant_client.close()

app = FastAPI(title="Campus RAG API Gateway Service (Hugging Face Edition)", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer: str

# -------------------------------------------------------------
# STEP 4: Core RAG Chat Processing Endpoint Logic
# -------------------------------------------------------------
@app.post("/api/chat", response_model=ChatResponse) 
async def chat_endpoint(request: ChatRequest):
    global model, qdrant_client, hf_client
    user_query = request.question.strip()
    
    if not user_query:
        raise HTTPException(status_code=400, detail="Question parameter field cannot be blank.")
        
    try:
        # Convert text query into numerical vector coordinates
        query_dense = model.encode(user_query).tolist()
        
        # Pull matching database metadata chunks from Qdrant local storage
        # Different qdrant-client versions expose different async search methods;
        # try the obvious ones and fall back gracefully.
        hits = []
        try:
            if hasattr(qdrant_client, "search"):
                hits = await qdrant_client.search(collection_name=COLLECTION_NAME, query_vector=query_dense, limit=3)
            elif hasattr(qdrant_client, "search_points"):
                hits = await qdrant_client.search_points(collection_name=COLLECTION_NAME, query_vector=query_dense, limit=3)
            elif hasattr(qdrant_client, "query_points"):
                resp = await qdrant_client.query_points(collection_name=COLLECTION_NAME, query=query_dense, limit=3)
                hits = getattr(resp, "points", resp)
            else:
                logger.error("No compatible search method found on AsyncQdrantClient instance.")
                hits = []
        except Exception:
            logger.exception("Error while querying Qdrant; proceeding with empty context.")
            hits = []

        retrieved_chunks = []
        for hit in hits or []:
            # hit may be an object with `.payload` or a dict
            payload = None
            if hasattr(hit, "payload"):
                payload = getattr(hit, "payload")
            elif isinstance(hit, dict):
                payload = hit.get("payload")

            if isinstance(payload, dict):
                text = payload.get("text")
                if text:
                    retrieved_chunks.append(text)

        context = "\n---\n".join(retrieved_chunks)

        # Log which chunks were retrieved for debugging/inspection (id, score, text)
        try:
            retrieved_meta = []
            for hit in hits or []:
                entry = {}
                entry_id = getattr(hit, "id", None) if hasattr(hit, "id") else (hit.get("id") if isinstance(hit, dict) else None)
                entry_score = getattr(hit, "score", None) if hasattr(hit, "score") else (hit.get("score") if isinstance(hit, dict) else None)
                # payload text
                payload = getattr(hit, "payload", None) if hasattr(hit, "payload") else (hit.get("payload") if isinstance(hit, dict) else None)
                entry_text = payload.get("text") if isinstance(payload, dict) else None
                entry["id"] = entry_id
                entry["score"] = entry_score
                entry["text"] = (entry_text[:200] + "...") if isinstance(entry_text, str) and len(entry_text) > 200 else entry_text
                retrieved_meta.append(entry)
            logger.info("Retrieved chunks for query '%s': %s", user_query, json.dumps(retrieved_meta, ensure_ascii=False))
        except Exception:
            logger.exception("Failed to log retrieved chunks metadata")
        
        system_instruction = (
            "You are the official automated chatbot assistant for our college campus website.\n"
            "Your task is to answer the student's question clearly, professionally, and factually "
            "using ONLY the provided reference context below.\n\n"
            f"CONTEXT FROM COLLEGE WEBSITE:\n{context}\n\n"
            "CRITICAL RULE: If the exact answer to the user's question cannot be found or reasonably inferred "
            "from the context provided above, state cleanly: 'I am sorry, but I couldn't find that specific information "
            "on the official college portal. Please contact the administrative department directly.' "
        )
        logger.debug(system_instruction)
        #  Send prompt to Hugging Face Cloud Inference Client using standardized Chat Completions API
        completion = hf_client.chat.completions.create(
            model=TARGET_MODEL,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_query}
            ],
            max_tokens=600,
            temperature=0.15
        )
        
        bot_response = completion.choices[0].message.content
        return ChatResponse(answer=bot_response)
        
    except Exception as e:
        logger.exception("Core API Inference Processing Fault Triggered: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal Operational Model Endpoint Fault: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)