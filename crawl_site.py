import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time

# Avoid SSL verification failures for self-signed or incomplete certificates
requests.packages.urllib3.disable_warnings()
from pypdf import PdfReader
import io
import re

START_URL = "https://www.jaihindcollege.com/"
DOMAIN = urlparse(START_URL).netloc

SEED_TARGETS = [
    "https://www.jaihindcollege.com/admission-notices/",
    "https://www.jaihindcollege.com/degree-college-post-graduate/",
    "https://www.jaihindcollege.com/structure-under-autonomy-post-graduate/",
    "https://www.jaihindcollege.com/admission-form-links/"
]
 
# Create directories to save the output locally
OUTPUT_DIR = "jai_hind_scraped_data"
TEXT_DIR = os.path.join(OUTPUT_DIR, "pages")
PDF_DIR = os.path.join(OUTPUT_DIR, "pdfs")
os.makedirs(TEXT_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)

visited_urls = set()
urls_to_visit = [START_URL] + SEED_TARGETS

def sanitize_filename(url):
    """Turns a URL into a safe, valid local filename."""
    path = urlparse(url).path
    if not path or path == "/":
        return "homepage.txt"
    filename = re.sub(r'[\\/*?:"<>|]', "_", path.strip("/"))
    return filename if filename.endswith(('.txt', '.pdf')) else f"{filename}.txt"

def extract_pdf_text(pdf_bytes):
    """Reads PDF binary data and extracts all readable text inside it."""
    try:
        pdf_file = io.BytesIO(pdf_bytes)
        reader = PdfReader(pdf_file)
        text = []
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text.append(extracted)
        return "\n".join(text)
    except Exception as e:
        return f"[Error parsing text from this PDF: {e}]"

print(f"Starting deep scrape of {START_URL}...")
print(f"Targeting explicitly: Masters Programs & Institutional Fee Data Structural Sub-paths.")
print(f"Data will be saved to the folder: '{os.path.abspath(OUTPUT_DIR)}'\n")

while urls_to_visit:
    current_url = urls_to_visit.pop(0)
    
    # Clean fragment identifiers (e.g., #section-1) to avoid scraping duplicate pages
    current_url = current_url.split('#')[0]
    
    if current_url in visited_urls:
        continue
        
    try:
        # Be respectful to the college server to avoid getting your IP banned
        time.sleep(0.5) 
        
        # 1. Handle PDF links directly
        if current_url.lower().endswith('.pdf') or "/uplaods" in current_url.lower():
            print(f"Downloading & Extracting PDF: {current_url}")
            visited_urls.add(current_url)
            
            response = requests.get(current_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15, verify=False)
            if response.status_code == 200:
                if response.headers.get('Content-Type', '').lower() != 'application/pdf' or current_url.lower().endswith('.pdf'):
                    pdf_text = extract_pdf_text(response.content)
                    filename = sanitize_filename(current_url)
                    if not filename.endswith('.txt'):
                        filename = filename.split('.')[0] + "_pdf_content.txt"
                
                    with open(os.path.join(PDF_DIR, filename), "w", encoding="utf-8") as f:
                        f.write(f"SOURCE URL: {current_url}\n\n" + pdf_text)
            continue

        # 2. Handle standard webpages
        response = requests.get(current_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15, verify=False)
        if response.status_code != 200:
            continue
            
        visited_urls.add(current_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Process and save web page text
        page_title = soup.title.string.strip() if soup.title else "Untitled Page"
        print(f"Scraping Page: {page_title} -> {current_url}")
        
        page_content = [f"URL: {current_url}", f"TITLE: {page_title}\n" + "="*40 + "\n"]
        
        # Grab all text tags
        elements = soup.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'li', 'td', 'th', 'span'])
        for element in elements:
            text = element.get_text().strip()
            # Avoid writing duplicate/empty lines if tags are nested
            if text and text not in page_content[-2:]: 
                page_content.append(text)
        
        filename = sanitize_filename(current_url)
        with open(os.path.join(TEXT_DIR, filename), "w", encoding="utf-8") as f:
            f.write("\n".join(page_content))
            
        # 3. Discover new links (Both subpages and PDF documents)
        for link in soup.find_all('a', href=True):
            href_val = link['href']
            absolute_url = urljoin(START_URL, link['href']).split('#')[0]
            
            # Filter to keep links internal to Jai Hind College domain only
            parsed_abs = urlparse(absolute_url)
            if parsed_abs.netloc == DOMAIN and absolute_url not in visited_urls:
                if absolute_url.lower().endswith('.pdf') or "/wp-content" in absolute_url.lower() or not any(absolute_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.css', '.js']):
                    if absolute_url not in urls_to_visit:
                        urls_to_visit.append(absolute_url)
    except Exception as e:
        print(f"skipping connection path {current_url}: {e}")

print(f"\nScraping completely finished.")
print(f"Total assets indexed: {len(visited_urls)}")