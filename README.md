# Jai Hind College Chatbot

A local knowledge-powered chatbot stack for Jai Hind College (Autonomous), Mumbai.
This project combines website scraping, chunking, semantic retrieval, and running a local Gradio chat UI.

## Contents

- `crawl_site.py` — scrape public website pages and PDFs into text files
- `chunk.py` — split scraped text into semantic chunks for indexing
- `server.py` — FastAPI backend with SQLite, Qdrant retrieval, and Ollama integration
- `gradio_app.py` — Gradio frontend for user interaction
- `init_db.py` — optional SQLite initialization helper
- `qdrant.py` — local Qdrant client example

## Architecture Overview

This chatbot is built as a classical RAG pipeline with the following stages:

1. **Scrape content** from website pages and PDFs (`crawl_site.py`)
2. **Chunk the scraped text** into smaller semantically meaningful pieces (`chunk.py`)
3. **Encode chunks and index them** in Qdrant using embeddings from `all-MiniLM-L6-v2`
4. **Run a FastAPI backend** that retrieves similar chunks for each user query and sends the assembled prompt to Ollama
5. **Serve a Gradio UI** that forwards user questions to the backend and shows conversation history

## What the Mentor Should Know

### 1. Session ID generation

- Session IDs are generated dynamically using the pattern:
  - `chat-<8 hex digits>`
- Example: `chat-5d1ac936`
- This is produced in `gradio_app.py` and in `server.py` when creating a new conversation.
- The session ID is used to group chat history in SQLite and to keep conversations separate.

### 2. Model and embedding dimensions

- The embedding model used in `server.py` is:
  - `sentence-transformers/all-MiniLM-L6-v2`
- Embedding vector dimension:
  - `384`
- Qdrant collection config:
  - `distance=Distance.COSINE`
  - `size=384`

### 3. Retrieval flow in `server.py`

- User queries are encoded to a dense embedding using `SentenceTransformer`.
- The code checks Qdrant client method compatibility:
  - `query_points(...)` if available
  - otherwise `search(...)`
- The top 3 hits are retrieved and their payload text is concatenated.
- The retrieved text is inserted into the system prompt as `VERIFIED CAMPUS INFORMATION:`.

### 4. Conversation memory and history

- Chat history is stored in SQLite `chatbot_history.db` in a single `messages` table.
- Each row contains:
  - `user_id`
  - `session_id`
  - `question`
  - `answer`
  - `chunk` (retrieved context or explanation)
- History is loaded for the last 3 turns when answering a new query.
- This enables the bot to preserve conversational context without re-querying the whole session.

### 5. Prompt design

- The backend creates a single `system_instruction` string that:
  - sets the persona to a senior student guide
  - specifies first-person conversational tone
  - defines verified campus facts and strict rules
  - instructs the model not to hallucinate or invent campus details
- Retrieved chunks are appended as supporting context.
- Past turns are inserted before the current user query.

## File-by-File Logic

### `crawl_site.py`

- Scrapes `https://www.jaihindcollege.com/` and seed pages
- Downloads HTML and PDF resources
- Removes noisy HTML elements: `header`, `footer`, `nav`, `script`, `style`, `aside`, `form`
- Extracts text from headings, paragraphs, lists, and table cells
- Writes page text files to:
  - `jai_hind_scraped_data/pages/`
  - `jai_hind_scraped_data/pdfs/`
- Files are tagged with `URL:` and `TITLE:` at the top

### `chunk.py`

- Reads all `.txt` files created by `crawl_site.py`
- Uses `RecursiveCharacterTextSplitter` with:
  - `chunk_size=800`
  - `chunk_overlap=120`
  - separators `['\n\n', '\n', '.', ' ', '']`
- Cleans whitespace and filters out chunks shorter than `80` characters
- Produces `jai_hind_chunks.json` with each item containing:
  - `content`
  - `source_url`
  - `title`
  - `type`
- Deduplicates chunks by content hash before saving

### `server.py`

- Starts with logging and SQLite initialization
- Creates a Qdrant collection at `./local_qdrant_storage` if missing
- Loads chunk data from `jai_hind_chunks.json` and builds embeddings
- Exposes API routes:
  - `POST /api/chat`
  - `GET /api/conversations`
  - `GET /api/conversations/{session_id}`
  - `POST /api/conversations/new`
- Uses `AsyncQdrantClient` and `aiosqlite`
- Chat endpoint logic:
  - retrieve recent history
  - perform vector search
  - build system prompt
  - call Ollama
  - store the chat turn

### `gradio_app.py`

- Uses Gradio Blocks for the frontend
- Maintains states for:
  - session ID
  - user ID
  - conversation history
  - saved conversation list
- Loads saved conversation summaries from the backend
- Sends user messages to `/api/chat`
- Updates the saved conversation dropdown after each turn
- Allows users to start a new chat session

### `init_db.py`

- Optional helper to create the SQLite schema manually
- Uses the same `messages` table structure as `server.py`

### `qdrant.py`

- Example local Qdrant client initialization
- Not used directly by the main application

## Installation

```bash
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install fastapi uvicorn requests httpx aiosqlite sentence-transformers qdrant-client gradio beautifulsoup4 pypdf langchain-text-splitters
```

## Recommended Run Order

1. `python crawl_site.py`
2. `python chunk.py`
3. `python server.py`
4. `python gradio_app.py`

## Runtime Requirements

- `Ollama` local endpoint at `http://127.0.0.1:11434`
- `jai_hind_chunks.json` available for ingestion
- `./local_qdrant_storage` writable by the app

## Questions Your Mentor May Ask

- How are session IDs generated and used?
- Why is the embedding dimension `384`?
- What is the role of Qdrant in this system?
- How does the backend assemble the prompt?
- How is conversation state stored and retrieved?
- Why is `presence_penalty` low and `temperature` set around `0.2`?
- What happens if the retrieved context is empty?
- How do scraped pages and PDFs become searchable knowledge?

## Troubleshooting

### `jai_hind_chunks.json` missing

Re-run:

```bash
python chunk.py
```

### Ollama connection failure

Verify Ollama is running on `http://127.0.0.1:11434`.

### Qdrant errors

Ensure `./local_qdrant_storage` exists and is writable.

### Gradio problems

Use the provided launch command and check the terminal for warnings.

## Notes

- `server.py` creates the DB automatically if needed.
- `init_db.py` is only required for manual DB reset.
- `qdrant.py` is a helper example, not required for the normal startup flow.
- The frontend is designed to keep session state and saved chat metadata separate.

## License

No license is specified.

