# chunk.py
import os
import json
import re
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ==============================
# CONFIG
# ==============================
BASE_DIR = "jai_hind_scraped_data"
FOLDERS_TO_PROCESS = ["pages", "pdfs"]
OUTPUT_FILE = "jai_hind_chunks.json"

MIN_CHUNK_LENGTH = 80   # filter tiny useless chunks

# ==============================
# TEXT SPLITTER (optimized)
# ==============================
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,          # better for MiniLM embeddings
    chunk_overlap=120,
    separators=["\n\n", "\n", ".", " ", ""]
)

compiled_chunks = []

print("🚀 Starting chunking pipeline...")

# ==============================
# HELPERS
# ==============================
def clean_text(text):
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_metadata(raw_content):
    """
    Extract URL and TITLE from scraper output
    """
    lines = raw_content.split("\n")

    source_url = "https://www.jaihindcollege.com/"
    title = "Unknown"

    for line in lines[:5]:
        if line.startswith("URL:"):
            source_url = line.replace("URL:", "").strip()
        elif line.startswith("TITLE:"):
            title = line.replace("TITLE:", "").strip()

    return source_url, title


# ==============================
# MAIN PROCESS
# ==============================
for sub_folder in FOLDERS_TO_PROCESS:

    folder_path = os.path.join(BASE_DIR, sub_folder)

    if not os.path.exists(folder_path):
        print(f"⚠️ Skipping missing folder: {folder_path}")
        continue

    print(f"\n📂 Processing folder: {sub_folder}")

    for file_name in os.listdir(folder_path):

        if not file_name.endswith(".txt"):
            continue

        file_path = os.path.join(folder_path, file_name)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_content = f.read()

            if not raw_content.strip():
                continue

            # ==============================
            # EXTRACT METADATA
            # ==============================
            source_url, title = extract_metadata(raw_content)

            # ==============================
            # CLEAN CONTENT
            # ==============================
            cleaned_content = clean_text(raw_content)

            # ==============================
            # SPLIT INTO CHUNKS
            # ==============================
            chunks = text_splitter.split_text(cleaned_content)

            for chunk in chunks:
                chunk = clean_text(chunk)

                # Skip useless chunks
                if len(chunk) < MIN_CHUNK_LENGTH:
                    continue

                compiled_chunks.append({
                    "content": chunk,
                    "source_url": source_url,
                    "title": title,
                    "type": "pdf" if sub_folder == "pdfs" else "webpage"
                })

        except Exception as e:
            print(f"⚠️ Error processing {file_name}: {e}")


# ==============================
# REMOVE DUPLICATE CHUNKS
# ==============================
print("\n🧹 Removing duplicate chunks...")

unique_chunks = []
seen = set()

for chunk in compiled_chunks:
    content_hash = hash(chunk["content"])

    if content_hash not in seen:
        unique_chunks.append(chunk)
        seen.add(content_hash)

# ==============================
# SAVE OUTPUT
# ==============================
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(unique_chunks, f, ensure_ascii=False, indent=2)

print(f"\n✅ Chunking complete!")
print(f"📊 Total chunks: {len(unique_chunks)}")
print(f"💾 Saved to: {OUTPUT_FILE}")