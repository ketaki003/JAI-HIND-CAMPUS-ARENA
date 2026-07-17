# Jai Hind Campus Arena - Resilient RAG Chatbot

An intelligent, stateful, and resilient Retrieval-Augmented Generation (RAG) chatbot developed for Jai Hind College (Autonomous), Mumbai. The system acts as a friendly official AI ambassador, utilizing local lightweight LLMs and a decoupled dual-database architecture to guarantee conversation continuity and low-latency performance.

---

## Key Features

* Decoupled Architecture: Qdrant handles high-dimensional semantic vectors (scraped web data), while SQLite manages chronological user session logs.
* Session Persistence (UID): Uses cryptographic browser-level session tokens (gr.State) to track independent user conversations seamlessly.
* Sliding-Window Memory: Limits context ingestion to the last 6 conversation turns, preventing token overflow or context window crashes on mini-LLM hardware.
* Fault Isolation: Even if the local generation engine hits a timeout or hardware bottleneck mid-stream, the conversational history remains entirely safe and uncorrupted on disk.

---

---

## Database Specifications

### 1. Relational Memory (SQLite)
Tracks individual text transactions chronologically mapped by user session variables:

| Column Name | Data Type | Modifiers | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique record ID |
| `session_id` | TEXT | NOT NULL (Indexed) | Session token string (UID) |
| `role` | TEXT | NOT NULL | Character indicator (`user` / `assistant`) |
| `content` | TEXT | NOT NULL | The structural body text |
| `timestamp` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Date and time log |

### 2. Vector Index (Qdrant)
* Collection Name: `JAI_HIND_COLLEGE_DATA`
* Embedding Model: `all-MiniLM-L6-v2` (SentenceTransformer)
* Vector Dimension: 384
* Distance Metric: Cosine Similarity

---

## Prerequisites & Setup

# 1. Installation
Clone the repository, create a virtual environment, and install the necessary dependencies:

-----bash 
----- > pip install install fastapi uvicorn qdrant-client sentence-transformers httpx pydantic aiosqlite gradio requests

# Run local 

ollama run qwen2.5:0.5b
ollama run tinyllama

-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
Running the Application
Step 1: Prepare Ingestion Data
Make sure your scraped data file jai_hind_chunks.json is located directly in your root project directory. The application lifespan manager will auto-detect it and construct the vector embedding database index on its very first launch.

Step 2: Spin Up the FastAPI Backend Server
Run the orchestrator backend. This initializes the SQLite databases, loads the SentenceTransformer framework, and establishes local client tunnels.

-----Bash
------> python server.py

Step 3: Launch the Gradio UI Frontend
---------Bash
---------> python gradio_app.py


