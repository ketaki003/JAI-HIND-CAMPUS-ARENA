# chunk.py
import os
import json
from langchain_text_splitters import RecursiveCharacterTextSplitter

# The core target folders populated by your new crawl_site.py
BASE_DIR = "jai_hind_scraped_data"
FOLDERS_TO_PROCESS = ["pages", "pdfs"]
OUTPUT_FILE = "jai_hind_chunks.json"

# Optimal parameters providing robust text blocks for compact models
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=900,
    chunk_overlap=120,
    length_function=len
)

compiled_chunks = []

print("Beginning multi-folder compilation for RAG injection...")

for sub_folder in FOLDERS_TO_PROCESS:
    target_path = os.path.join(BASE_DIR, sub_folder)
    
    if not os.path.exists(target_path):
        print(f"⚠️ Directory pathway omitted (not found): {target_path}")
        continue
        
    print(f"Processing scraped files inside: '{sub_folder}'...")
    
    for file_name in os.listdir(target_path):
        if file_name.endswith(".txt"):
            file_filepath = os.path.join(target_path, file_name)
            
            with open(file_filepath, "r", encoding="utf-8") as f:
                raw_content = f.read()
                
            # Attempt to safely parse out the URL stamped by the crawler
            lines = raw_content.split("\n")
            source_url = "https://www.jaihindcollege.com/"
            
            for line in lines[:3]:
                if line.startswith("SOURCE URL:") or line.startswith("URL:"):
                    source_url = line.replace("SOURCE URL:", "").replace("URL:", "").strip()
                    break
            
            # Divide text using hierarchical layout boundaries
            chunks = text_splitter.split_text(raw_content)
            
            for chunk in chunks:
                compiled_chunks.append({
                    "content": chunk.strip(),
                    "source_url": source_url,
                    "type": "document" if sub_folder == "pdfs" else "webpage"
                })

# Save the unified payload out to disk
with open(OUTPUT_FILE, "w", encoding="utf-8") as out_f:
    json.dump(compiled_chunks, out_f, ensure_ascii=False, indent=4)

print(f"\nSuccessfully compiled {len(compiled_chunks)} text fragments into '{OUTPUT_FILE}'.")
print("You can now clear the './local_qdrant_storage' folder and reboot server.py to sync the data.")