# chunk.py
import os
import json
import re
from langchain_text_splitters import MarkdownTextSplitter

# ==============================
# CONFIG
# ==============================
BASE_DIR = "jai_hind_scraped_data"
FOLDERS_TO_PROCESS = ["pages", "pdfs"]
OUTPUT_FILE = "jai_hind_chunks.json"

MIN_CHUNK_LENGTH = 60

# Split along Markdown section headers
text_splitter = MarkdownTextSplitter(
    chunk_size=700,
    chunk_overlap=100
)

compiled_chunks = []

def extract_metadata(raw_content):
    lines = raw_content.split("\n")
    source_url = "https://www.jaihindcollege.com/"
    title = "Unknown"

    for line in lines[:5]:
        if line.startswith("URL:"):
            source_url = line.replace("URL:", "").strip()
        elif line.startswith("TITLE:"):
            title = line.replace("TITLE:", "").strip()

    return source_url, title


print(" Starting Markdown-aware chunking pipeline...")

for sub_folder in FOLDERS_TO_PROCESS:
    folder_path = os.path.join(BASE_DIR, sub_folder)

    if not os.path.exists(folder_path):
        print(f" Skipping missing folder: {folder_path}")
        continue

    print(f"\n Processing folder: {sub_folder}")

    for file_name in os.listdir(folder_path):
        if not (file_name.endswith(".md") or file_name.endswith(".txt")):
            continue

        file_path = os.path.join(folder_path, file_name)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_content = f.read()

            if not raw_content.strip():
                continue

            source_url, title = extract_metadata(raw_content)

            # Separate metadata header from body
            content_body = "\n".join([
                line for line in raw_content.split("\n") 
                if not line.startswith("URL:") and not line.startswith("TITLE:")
            ]).strip()

            chunks = text_splitter.split_text(content_body)

            for chunk in chunks:
                chunk_clean = chunk.strip()

                if len(chunk_clean) < MIN_CHUNK_LENGTH:
                    continue

                compiled_chunks.append({
                    "content": chunk_clean,
                    "source_url": source_url,
                    "title": title,
                    "type": "pdf" if sub_folder == "pdfs" else "webpage"
                })

        except Exception as e:
            print(f" Error processing {file_name}: {e}")

# Deduplication
print("\n Removing duplicate chunks...")
unique_chunks = []
seen_hashes = set()

for chunk in compiled_chunks:
    chunk_hash = hash(chunk["content"])
    if chunk_hash not in seen_hashes:
        unique_chunks.append(chunk)
        seen_hashes.add(chunk_hash)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(unique_chunks, f, ensure_ascii=False, indent=2)

print(f"\n Chunking complete!")
print(f" Total unique chunks generated: {len(unique_chunks)}")
print(f" Output saved to: {OUTPUT_FILE}")