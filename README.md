# Jai Hind College Automated Chatbot System

A production-grade, local Retrieval-Augmented Generation (RAG) chatbot system built for **Jai Hind College (Autonomous), Mumbai**. The system combines web scraping, vector embeddings, local vector search, SQLite session state tracking, and local LLM inferencing via Ollama, along with an execution mode toggle for direct LLM API comparison.

---

## Technical Architecture

```
[ Gradio UI ] (Port 7860)
      │
      ├── Execution Mode: "RAG Pipeline (FastAPI)"
      │         │
      │         ▼
      │   [ FastAPI Gateway Server ] (Port 8000)
      │         ├── 1. Embed Query (sentence-transformers / all-MiniLM-L6-v2)
      │         ├── 2. Vector Search (Qdrant Local Storage)
      │         ├── 3. Load Chat Memory (SQLite: chatbot_history.db)
      │         ├── 4. Generate AI Title (Ollama API)
      │         └── 5. Send RAG Prompt (Ollama / qwen2.5:0.5b or tinyllama)
      │
      └── Execution Mode: "Direct API Call (Ollama)"
                │
                ▼
          [ Ollama LLM Engine Direct ] (Port 11434)
                └── Bypasses Vector DB, Prompt Engineering, & SQLite History
```

---

## Key Features

* **Dual Execution Modes:**
  * **RAG Pipeline Mode:** Full context-augmented answering using vector search over official campus documents and persistent chat history.
  * **Direct LLM API Mode:** Direct query bypass straight to the Ollama endpoint for performance benchmarking and hallucination comparison.
* **Local Private Inferencing:** Fully offline-capable LLM processing through Ollama without sending sensitive data to external cloud APIs.
* **Semantic Vector Retrieval:** Uses `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions) and a local Qdrant instance for cosine-similarity semantic retrieval.
* **Persistent Conversation History:** Multi-user conversation storage backed by SQLite (`chatbot_history.db`) indexed by `user_id` and `session_id`.
* **Automatic Chat Summarization:** Automatically generates 3-to-4 word conversational titles for saved chat sessions using background LLM inference.
* **Strict Anti-Hallucination Controls:** Custom system prompt design enforcing strict ground-truth facts, explicit non-existence rules for missing facilities, and low temperature settings (`0.2`).

---

## Repository Structure

```text
.
├── crawl_site.py          # Web & PDF scraper for Jai Hind College website
├── chunk.py               # Text splitter and chunk deduplication generator
├── jai_hind_chunks.json   # Processed JSON database of semantic text chunks
├── server.py              # FastAPI server, Qdrant indexing, and Ollama integration
├── gradio_app.py          # Interactive web UI built with Gradio Blocks (supports Direct API mode)
├── init_db.py             # Database schema setup helper script
├── test_db.py             # Unit test script for SQLite operations
├── app.log                # Application runtime log file
└── error.log              # Error tracking log file
```

---

## Prerequisites

* **Python:** 3.11 or higher
* **Ollama:** Installed and running locally on port `11434`
* **Local Models:** `qwen2.5:0.5b` or `tinyllama` pulled via Ollama CLI

---

## Installation

1. **Clone the Repository and Navigate to Root:**
   ```bash
   cd jai-hind-chatbot
   ```

2. **Create and Activate a Virtual Environment:**
   * **Windows:**
     ```bash
     python -m venv venv
     venv\Scripts\activate
     ```
   * **Linux/macOS:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install Dependencies:**
   ```bash
   pip install --upgrade pip
   pip install fastapi uvicorn requests httpx aiosqlite sentence-transformers qdrant-client gradio beautifulsoup4 pypdf langchain-text-splitters
   ```

4. **Pull Ollama Models:**
   ```bash
   ollama pull qwen2.5:0.5b
   ollama pull tinyllama
   ```

---

## Step-by-Step Execution Guide

### Step 1: Web Scraping and Data Extraction
Extract text content from website pages and PDF files into `jai_hind_scraped_data/`:
```bash
python crawl_site.py
```

### Step 2: Chunk Generation
Split extracted text into structured, deduplicated semantic chunks saved in `jai_hind_chunks.json`:
```bash
python chunk.py
```

### Step 3: Initialize Database (Optional)
Explicitly set up the SQLite schema for history storage (`chatbot_history.db`):
```bash
python init_db.py
```
*(Note: `server.py` automatically initializes the database schema if missing).*

### Step 4: Start Backend API Gateway
Run the FastAPI backend server on `http://127.0.0.1:8000`:
```bash
python server.py
```
*On initial run, `server.py` will read `jai_hind_chunks.json`, vector-encode all entries, and build the local Qdrant collection at `./local_qdrant_storage`.*

### Step 5: Start Frontend UI
Launch the Gradio user interface on `http://127.0.0.1:7860`:
```bash
python gradio_app.py
`---

## System Configuration Details

| Parameter | Configuration / Value | File / Source |
| :--- | :--- | :--- |
| **Embedding Model** | `sentence-transformers/all-MiniLM-L6-v2` | `server.py` |
| **Vector Dimension** | 384 | `server.py` |
| **Distance Metric** | Cosine Similarity | `server.py` |
| **Qdrant Storage Path** | `./local_qdrant_storage` | `server.py` |
| **Vector Collection Name** | `JAI_HIND_COLLEGE_DATA` | `server.py` |
| **Database File** | `chatbot_history.db` | `init_db.py`, `server.py` |
| **Backend API Gateway Host** | `http://127.0.0.1:8000` | `server.py`, `gradio_app.py` |
| **Direct Ollama Host** | `http://127.0.0.1:11434` | `gradio_app.py`, `server.py` |
| **Frontend UI Host** | `http://127.0.0.1:7860` | `gradio_app.py` |
| **Temperature** | `0.2` | `server.py`, `gradio_app.py` |
| **Top K Retrieved Chunks** | 3 | `server.py` |

---

## Execution Modes & API Call Logic

In `gradio_app.py`, users can toggle between two primary execution pathways:

### 1. RAG Pipeline Mode (FastAPI Backend)
* **Endpoint:** `POST /api/chat`
* **Workflow:**
  1. Gradio sends prompt, `session_id`, and `user_id` to FastAPI gateway on port `8000`.
  2. Backend performs dense vector query against local Qdrant collection (`JAI_HIND_COLLEGE_DATA`).
  3. Top 3 matching content chunks are retrieved and injected into a strict system prompt.
  4. Context-infused prompt is sent to Ollama (`http://127.0.0.1:11434/v1/chat/completions`).
  5. Response turn is logged into SQLite (`chatbot_history.db`) for multi-turn chat memory.

### 2. Direct API Call Mode (Bypass Mode)
* **Endpoint:** `POST http://127.0.0.1:11434/v1/chat/completions`
* **Workflow:**
  1. Gradio sends raw user prompt directly to Ollama endpoint, bypassing FastAPI and Qdrant.
  2. Bypasses vector database retrieval and custom ground-truth system instructions.
  3. Ideal for benchmarking answer quality, latency, and demonstrating hallucination differences between raw base LLMs vs. RAG-augmented LLMs.

---

## API Gateway Endpoints (`server.py`)

### 1. Send Chat Message (RAG)
* **Endpoint:** `POST /api/chat`
* **Payload:**
  ```json
  {
    "question": "What courses are offered in MSc?",
    "selected_model": "qwen2.5:0.5b",
    "session_id": "chat-5d1ac936",
    "user_id": "user1"
  }
  ```
* **Response:**
  ```json
  {
    "answer": "We offer postgraduate programs such as M.Sc. Chemistry and M.Sc. Big Data Analytics..."
  }
  ```

### 2. Get All User Conversations
* **Endpoint:** `GET /api/conversations?user_id=user1`
* **Response:** Returns list of historical chat sessions with auto-generated AI titles and timestamps.

### 3. Load Specific Session Thread
* **Endpoint:** `GET /api/conversations/{session_id}?user_id=user1`
* **Response:** Returns all past turns associated with the requested `session_id`.

### 4. Create New Conversation
* **Endpoint:** `POST /api/conversations/new`
* **Response:** Generates a new unique `session_id` string formatted as `chat-<8 hex digits>`.

---

## Database Architecture & Session Management (`chatbot_history.db`)

The conversation history layer handles multi-user session tracking, chat context reloading, and automatic topic naming.

### 1. Database Schema
Table: **`messages`**

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Auto-incrementing turn ID |
| `user_id` | `TEXT NOT NULL` | Identifier grouping conversations by user |
| `session_id` | `TEXT NOT NULL` | Unique identifier for a specific chat thread |
| `question` | `TEXT NOT NULL` | The exact prompt entered by the user |
| `answer` | `TEXT NOT NULL` | The generated LLM response |
| `chunk` | `TEXT` | Semantic text context retrieved from Qdrant |
| `timestamp` | `DATETIME` | Default UTC timestamp (`CURRENT_TIMESTAMP`) |

### 2. Index Optimization
To support fast history lookups across multiple sessions and users, a composite index is maintained:
```sql
CREATE INDEX IF NOT EXISTS idx_user_session ON messages(user_id, session_id);
```

### 3. Generation Logic: User ID & Session ID

#### User ID (`user_id`)
* **Default Value:** Defaults to `"user1"` in UI and API parameters for single-user development testing.
* **Dynamic Client-Side Generation:** In `gradio_app.py`, a unique client user identifier can be initialized dynamically via:
  ```python
  user_id = f"user-{uuid.uuid4().hex[:6]}"
  ```
* **Role in DB:** Acts as the top-level isolation key so a single user can list, view, or filter only their specific chat threads.

#### Session ID (`session_id`)
* **Format Structure:** `chat-<8 hex digits>` (e.g., `chat-5d1ac936`).
* **Generation Workflow:**
  * **Frontend Initialization:** When `gradio_app.py` boots, it generates an initial active session using `f"chat-{uuid.uuid4().hex[:8]}"`.
  * **New Chat Button:** Clicking "➕ New Chat" triggers `POST /api/conversations/new`, where the backend creates a fresh UUID hex string and passes it back to the client.
* **Role in DB:** Groups individual question-and-answer exchanges into a unified conversation thread.

### 4. Automatic AI Chat Summarization (Topic Titles)
When listing past conversations via `GET /api/conversations`, the system automatically assigns a readable title to each `session_id`:
1. The backend retrieves the **first user prompt** submitted in that `session_id`.
2. It sends a fast background completion request to Ollama using `qwen2.5:0.5b`:
   > *"Summarize the following question into a short, concise 3 to 4 word chat topic title..."*
3. The resulting clean title is displayed directly inside the Gradio **"Saved Conversations"** dropdown menu.

### 5. Conversational Memory Window
When a user asks a new question in RAG mode, `server.py` queries `chatbot_history.db` for the **last 3 turns (limit=3)** matching the given `user_id` and `session_id`. These prior turns are prepended to the current user prompt before sending the full payload to Ollama, enabling multi-turn context retention without exceeding context limits.

---

## Prompt Engineering Strategy

To ensure zero-hallucination and authoritative campus information in RAG mode, the system prompt injected into Ollama enforces:

1. **Identity & Persona:** Senior student ambassador at Jai Hind College (Autonomous), Mumbai, speaking in first person ("I", "we", "our campus").
2. **Ground Truth Overrides:** Hardcoded verifiable facts regarding address, leadership, and official contact phone numbers.
3. **Negative Constraint Rules:** Explicit negative directives regarding missing campus infrastructure (e.g., confirming the lack of on-campus swimming pools or private hostels).
4. **Source Masking:** Mandate forbidding the LLM from referencing technical terms such as "provided context", "database", or "retrieved documents" in output.

---

## Troubleshooting

### Error: `jai_hind_chunks.json` missing on server startup
* **Cause:** The backend lifecycle attempted to create Qdrant embeddings before data extraction was run.
* **Fix:** Run `python chunk.py` to generate the JSON dataset prior to starting `server.py`.

### Error: Connection Failed to Ollama (`http://127.0.0.1:11434`)
* **Cause:** Ollama service is stopped or port `11434` is blocked.
* **Fix:** Start Ollama service locally and verify availability in browser via `http://127.0.0.1:11434`.

### Error: `Connection Failed to FastAPI backend`
* **Cause:** `gradio_app.py` cannot reach `server.py` on port `8000` while in RAG mode.
* **Fix:** Ensure `server.py` is running simultaneously in another terminal window.

---

## License

Internal Development Project - Jai Hind College (Autonomous), Mumbai.