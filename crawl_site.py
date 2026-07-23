import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import io
import re
import logging
from pypdf import PdfReader

# ==============================
# CONFIGURATION
# ==============================
START_URL = "https://www.jaihindcollege.com/"
DOMAIN = urlparse(START_URL).netloc

SEED_TARGETS = [
    "https://www.jaihindcollege.com/contact-us/",
    "https://www.jaihindcollege.com/admission-notices/",
    "https://www.jaihindcollege.com/degree-college-post-graduate/",
    "https://www.jaihindcollege.com/structure-under-autonomy-post-graduate/",
    "https://www.jaihindcollege.com/admission-form-links/"
]

IMPORTANT_KEYWORDS = [
    "admission", "course", "fee", "contact",
    "department", "faculty", "program", "syllabus"
]

MAX_PAGES = 200   # limit crawl size

# ==============================
# SETUP
# ==============================
requests.packages.urllib3.disable_warnings()

OUTPUT_DIR = "jai_hind_scraped_data"
TEXT_DIR = os.path.join(OUTPUT_DIR, "pages")
PDF_DIR = os.path.join(OUTPUT_DIR, "pdfs")

os.makedirs(TEXT_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

visited_urls = set()
urls_to_visit = [START_URL] + SEED_TARGETS


# ==============================
# HELPERS
# ==============================
def sanitize_filename(url):
    path = urlparse(url).path
    if not path or path == "/":
        return "homepage.txt"
    filename = re.sub(r'[\\/*?:"<>|]', "_", path.strip("/"))
    return filename if filename.endswith(".txt") else f"{filename}.txt"


def clean_text(text):
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_pdf_text(pdf_bytes):
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
        return f"[PDF PARSE ERROR: {e}]"


# ==============================
# SCRAPER START
# ==============================
logging.info(f"Starting scrape: {START_URL}")

while urls_to_visit:

    # LIMIT CONTROL
    if len(visited_urls) >= MAX_PAGES:
        logging.info("Reached MAX_PAGES limit. Stopping crawl.")
        break

    current_url = urls_to_visit.pop(0).split('#')[0]

    if current_url in visited_urls:
        continue

    try:
        time.sleep(0.5)

        # ==============================
        # HANDLE PDF
        # ==============================
        if current_url.lower().endswith(".pdf") or "/uploads" in current_url.lower():
            logging.info(f"Processing PDF: {current_url}")
            visited_urls.add(current_url)

            response = requests.get(current_url, timeout=15, verify=False)

            if response.status_code == 200 and 'application/pdf' in response.headers.get('Content-Type', '').lower():
                pdf_text = extract_pdf_text(response.content)

                filename = sanitize_filename(current_url).replace(".txt", "_pdf.txt")

                with open(os.path.join(PDF_DIR, filename), "w", encoding="utf-8") as f:
                    f.write(f"URL: {current_url}\n\n{pdf_text}")

            continue

        # ==============================
        # HANDLE HTML PAGE
        # ==============================
        response = requests.get(current_url, timeout=15, verify=False)

        if response.status_code != 200:
            continue

        visited_urls.add(current_url)

        soup = BeautifulSoup(response.text, "html.parser")

        # REMOVE NOISE
        for tag in soup(['header', 'footer', 'nav', 'script', 'style', 'aside', 'form']):
            tag.decompose()

        title = soup.title.string.strip() if soup.title else "Untitled"

        logging.info(f"Scraping: {title} | {current_url}")

        page_content = [
            f"URL: {current_url}",
            f"TITLE: {title}",
            "=" * 50
        ]

        # ==============================
        # EXTRACT TEXT (DEDUPED)
        # ==============================
        seen_text = set()

        elements = soup.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'li', 'td', 'th'])

        for element in elements:
            text = clean_text(element.get_text())

            if text and text not in seen_text:
                page_content.append(text)
                seen_text.add(text)

        # SAVE FILE
        filename = sanitize_filename(current_url)

        with open(os.path.join(TEXT_DIR, filename), "w", encoding="utf-8") as f:
            f.write("\n".join(page_content))

        # ==============================
        # DISCOVER NEW LINKS
        # ==============================
        for link in soup.find_all("a", href=True):

            absolute_url = urljoin(START_URL, link["href"]).split('#')[0]
            parsed = urlparse(absolute_url)

            if parsed.netloc != DOMAIN:
                continue

            if absolute_url in visited_urls:
                continue

            # FILTER OUT MEDIA FILES
            if any(absolute_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.css', '.js']):
                continue

            # PRIORITIZE IMPORTANT PAGES
            if any(keyword in absolute_url.lower() for keyword in IMPORTANT_KEYWORDS):
                if absolute_url not in urls_to_visit:
                    urls_to_visit.append(absolute_url)
            else:
                # Optional: still crawl but lower priority
                if absolute_url not in urls_to_visit:
                    urls_to_visit.append(absolute_url)

    except Exception as e:
        logging.warning(f"Skipping {current_url} due to error: {e}")


logging.info(f"Scraping completed. Total pages: {len(visited_urls)}")