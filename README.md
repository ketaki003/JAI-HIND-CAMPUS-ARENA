
# Jai Hind College Chatbot

This repository contains a local chatbot stack for Jai Hind College (Autonomous), Mumbai.
The pipeline includes:

- `crawl_site.py` — scrape website pages and PDFs into text files
- `chunk.py` — convert scraped text into semantic chunks
- `server.py` — FastAPI backend that builds embeddings, queries Qdrant, and calls Ollama
- `gradio_app.py` — Gradio frontend to interact with the chatbot
- `init_db.py` — optional SQLite initialization helper
- `qdrant.py` — simple Qdrant client example for local storage

## Prerequisites

Install Python 3.11+ and create a virtual environment before running the project.

Recommended packages include:

- `fastapi`
- `uvicorn`
- `requests`
- `httpx`
- `aiosqlite`
- `sentence-transformers`
- `qdrant-client`
- `gradio`
- `beautifulsoup4`
- `pypdf`
- `langchain-text-splitters`

You can install dependencies with pip. Example:

```bash
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install fastapi uvicorn requests httpx aiosqlite sentence-transformers qdrant-client gradio beautifulsoup4 pypdf langchain-text-splitters
```

## Setup and Data Pipeline

### 1. Crawl the website

Run the scraper to collect site pages and PDF text into `jai_hind_scraped_data`:

```bash
python crawl_site.py
```

This generates text files under:

- `jai_hind_scraped_data/pages/`
- `jai_hind_scraped_data/pdfs/`

### 2. Chunk the scraped text

Create semantic chunks from the scraped data and write them to `jai_hind_chunks.json`:

```bash
python chunk.py
```

### 3. Initialize the database (optional)

If you want to create or reset the SQLite history database manually:

```bash
python init_db.py
```

Normally, `server.py` will create `chatbot_history.db` automatically on startup.

## Running the Backend

The backend depends on a local Ollama chat completion endpoint at `http://127.0.0.1:11434`.

Start the FastAPI server:

```bash
python server.py
```

If the Qdrant collection does not exist yet, the server will read `jai_hind_chunks.json`, encode the chunks using `all-MiniLM-L6-v2`, and create a local Qdrant collection at `./local_qdrant_storage`.

## Running the Frontend

Start the Gradio UI:

```bash
python gradio_app.py
```

Then open the local Gradio URL shown in the terminal (default: `http://127.0.0.1:7860`).

## How It Works

- `gradio_app.py` sends user messages to the FastAPI endpoint at `/api/chat`.
- `server.py` retrieves recent conversation history from SQLite and performs a Qdrant vector search using the current query.
- The backend assembles a system prompt, appends retrieved context and chat history, and forwards the request to Ollama.
- The response is stored in SQLite and returned to the frontend.

## Important Files

- `crawl_site.py` — scraper for website and PDF content
- `chunk.py` — text chunking into JSON for embedding ingestion
- `server.py` — backend API, semantic retrieval, Ollama integration
- `gradio_app.py` — user-facing chat interface
- `init_db.py` — optional SQLite schema setup
- `qdrant.py` — local Qdrant client example

## Notes

- Ensure Ollama is running before starting `server.py`.
- Ensure `jai_hind_chunks.json` exists before the first backend startup.
- If the app cannot connect to Qdrant, check that the local storage path is writable and that the collection is being created.
- The Gradio app currently uses dynamic session IDs and saved conversation dropdown state.

## Troubleshooting

### Missing chunks file

If `server.py` exits with a missing `jai_hind_chunks.json` error, re-run:

```bash
python chunk.py
```

### Ollama connection failures

If the backend cannot reach Ollama, verify that the service is running on port `11434` and that local networking is allowed.

### Gradio warnings

If Gradio warns about theme parameters, the current setup passes `theme` to `launch()` instead of `Blocks()`.

## License

No license is specified.
=======

