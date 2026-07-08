# scraper.py
import requests
from bs4 import BeautifulSoup
import json
import re
import urllib3
import io
from pypdf import PdfReader

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

urls = [
    "https://jaihindcollege.com/",
    "https://jaihindcollege.com/admissions/",
    "https://www.jaihindcollege.com/degree-college-post-graduate/",
    "https://www.jaihindcollege.com/degree-college-self-financed/",
    "https://www.jaihindcollege.com/degree-college-aided/",
    "https://www.jaihindcollege.com/examination/",
    "https://www.jaihindcollege.com/general-notices/",
    "https://jaihindcollege.com/departments/",
    "https://jaihindcollege.com/post-graduate-admissions/", 
    "https://jaihindcollege.com/jaihindcollege-new/msc-big-data-analytics/", 
    "https://jaihindcollege.com/about-us/",
    "https://www.jaihindcollege.com/code-of-conduct/",
    "https://www.jaihindcollege.com/legacy/",
    "https://www.jaihindcollege.com/from-the-principals-desk/",
    "https://jaihindcollege.com/wp-content/uploads/2026/05/Jai-Hind-College-Handbook.pdf",
    "https://www.jaihindcollege.com/cells-and-societies-2/",
    "https://www.jaihindcollege.com/autonomy/"
]

headers = {"User-Agent": "Mozilla/5.0"}
structured_dataset = []
seen_texts = set()

def clean_and_normalize(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def process_pdf_content(pdf_target_url: str):
    print(f"📥 Extracting Binary Data Layer from PDF: {pdf_target_url}")
    try:
        pdf_response = requests.get(pdf_target_url, headers=headers, verify=False)
        pdf_response.raise_for_status()
        
        with io.BytesIO(pdf_response.content) as open_pdf:
            reader = PdfReader(open_pdf)
            total_pages = len(reader.pages)
            print(f"   ℹ Processing {total_pages} pages...")
            
            for page_idx, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if not page_text:
                    continue
                
                cleaned_text = clean_and_normalize(page_text)
                if len(cleaned_text) > 25 and cleaned_text not in seen_texts:
                    seen_texts.add(cleaned_text)
                    structured_dataset.append({
                        "id": len(structured_dataset) + 1,
                        "text": f"Document: {pdf_target_url.split('/')[-1]} -> Page {page_idx + 1} Content: {cleaned_text}",
                        "source": f"Scraped PDF Document: {pdf_target_url} (Page {page_idx + 1})"
                    })
    except Exception as pdf_err:
        print(f"   ⚠️ Could not read or process PDF {pdf_target_url}: {pdf_err}")

for url in urls:
    if url.lower().endswith(".pdf"):
        process_pdf_content(url)
        continue

    print(f"\n🌐 Scraping Webpage: {url}")
    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        page_title = clean_and_normalize(soup.title.get_text()) if soup.title else "Jai Hind College Portal"
        current_heading = "General Overview"

        # 🚀 1. EXTRACT TABLES IN CLEAN MARKDOWN LAYOUT
        for table in soup.find_all("table"):
            table_lines = []
            for row in table.find_all("tr"):
                cells = [clean_and_normalize(cell.get_text()) for cell in row.find_all(["td", "th"])]
                if cells:
                    table_lines.append(" | ".join(cells))
            
            markdown_table = "\n".join(table_lines)
            if len(markdown_table) > 30 and markdown_table not in seen_texts:
                seen_texts.add(markdown_table)
                structured_dataset.append({
                    "id": len(structured_dataset) + 1,
                    "text": f"Page: {page_title} -> Structured Table Reference Data:\n{markdown_table}",
                    "source": f"Scraped Table Matrix: {url}"
                })

        # Remove elements inside data tables to avoid noisy chunk duplication
        for table in soup.find_all("table"):
            table.decompose()

        # 🚀 2. CONTEXT-ENRICHED EXTRACT VIA WINDOW TRACKING
        elements = soup.find_all(["p", "li", "h1", "h2", "h3", "span"])
        for el in elements:
            if el.name in ["h1", "h2", "h3"]:
                current_heading = clean_and_normalize(el.get_text())
                continue
                
            cleaned_el_text = clean_and_normalize(el.get_text())
            
            # Avoid picking up parent wrappers or micro text scraps
            if 25 < len(cleaned_el_text) < 1200 and cleaned_el_text not in seen_texts:
                seen_texts.add(cleaned_el_text)
                enriched_chunk_text = f"Page Context: {page_title} -> Section: {current_heading} -> Detail: {cleaned_el_text}"
                
                structured_dataset.append({
                    "id": len(structured_dataset) + 1,
                    "text": enriched_chunk_text,
                    "source": f"Scraped Webpage: {url}"
                })

        # 3. Handle discovered inline hyperlinked PDF targets dynamically
        for link in soup.find_all("a", href=True):
            href = link["href"].strip()
            if href.lower().endswith(".pdf"):
                pdf_url = href if href.startswith("http") else f"https://jaihindcollege.com{href}"
                process_pdf_content(pdf_url)

    except Exception as e:
        print(f"❌ Error accessing webpage path {url}: {e}")

print(f"\n💾 Writing {len(structured_dataset)} extracted chunks to college_data.json...")
with open("college_data.json", "w", encoding="utf-8") as file:
    json.dump(structured_dataset, file, indent=4, ensure_ascii=False)

print(f"🎉 Pipeline Execution Complete! JSON file built cleanly.")