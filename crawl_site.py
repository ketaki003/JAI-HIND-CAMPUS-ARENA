# crawl.py
import asyncio
import os
import re
import logging
from urllib.parse import urlparse
import requests
from pypdf import PdfReader

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import PruningContentFilter

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

MAX_PAGES = 200
OUTPUT_DIR = "jai_hind_scraped_data"
PAGES_DIR = os.path.join(OUTPUT_DIR, "pages")
PDF_DIR = os.path.join(OUTPUT_DIR, "pdfs")

os.makedirs(PAGES_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def sanitize_filename(url):
    path = urlparse(url).path
    if not path or path == "/":
        return "homepage.md"
    filename = re.sub(r'[\\/*?:"<>|]', "_", path.strip("/"))
    return f"{filename}.md"


def extract_pdf_text(pdf_bytes):
    try:
        from io import BytesIO
        reader = PdfReader(BytesIO(pdf_bytes))
        text = [page.extract_text() for page in reader.pages if page.extract_text()]
        return "\n\n".join(text)
    except Exception as e:
        return f"[PDF PARSE ERROR: {e}]"


async def main():
    visited_urls = set()
    urls_to_visit = [START_URL] + SEED_TARGETS

    # Set up Crawl4AI with PruningContentFilter to eliminate layout noise
    md_generator = DefaultMarkdownGenerator(
        content_filter=PruningContentFilter(threshold=0.45, min_word_threshold=10)
    )

    browser_config = BrowserConfig(headless=True)
    run_config = CrawlerRunConfig(
        markdown_generator=md_generator,
        word_count_threshold=20
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        while urls_to_visit and len(visited_urls) < MAX_PAGES:
            current_url = urls_to_visit.pop(0).split('#')[0]

            if current_url in visited_urls:
                continue

            # ==============================
            # HANDLE PDF DOCUMENTS
            # ==============================
            if current_url.lower().endswith(".pdf") or "/uploads" in current_url.lower():
                logging.info(f"Fetching PDF: {current_url}")
                visited_urls.add(current_url)
                try:
                    res = requests.get(current_url, timeout=15, verify=False)
                    if res.status_code == 200 and 'application/pdf' in res.headers.get('Content-Type', '').lower():
                        pdf_md = extract_pdf_text(res.content)
                        filename = sanitize_filename(current_url).replace(".md", "_pdf.md")
                        with open(os.path.join(PDF_DIR, filename), "w", encoding="utf-8") as f:
                            f.write(f"URL: {current_url}\nTITLE: PDF Document\n\n{pdf_md}")
                except Exception as e:
                    logging.warning(f"Error fetching PDF {current_url}: {e}")
                continue

            # ==============================
            # CRAWL WEBPAGE USING CRAWL4AI
            # ==============================
            logging.info(f"Crawling: {current_url}")
            visited_urls.add(current_url)

            try:
                result = await crawler.arun(url=current_url, config=run_config)

                if not result.success:
                    continue

                # Get clean markdown output
                markdown_content = result.markdown.fit_markdown or result.markdown.raw_markdown

                if not markdown_content:
                    continue

                # Save markdown output
                filename = sanitize_filename(current_url)
                file_path = os.path.join(PAGES_DIR, filename)

                page_title = result.metadata.get("title", "Jai Hind College") if result.metadata else "Jai Hind College"

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(f"URL: {current_url}\nTITLE: {page_title}\n\n{markdown_content}")

                # ==============================
                # DISCOVER NEW LINKS
                # ==============================
                for link in result.links.get("internal", []):
                    clean_link = link["href"].split('#')[0]
                    parsed = urlparse(clean_link)

                    if parsed.netloc == DOMAIN and clean_link not in visited_urls:
                        if any(clean_link.lower().endswith(ext) for ext in ['.jpg', '.png', '.css', '.js']):
                            continue

                        # Prioritize core informational pages
                        if any(kw in clean_link.lower() for kw in IMPORTANT_KEYWORDS):
                            urls_to_visit.insert(0, clean_link)
                        elif clean_link not in urls_to_visit:
                            urls_to_visit.append(clean_link)

            except Exception as e:
                logging.warning(f"Failed to crawl {current_url}: {e}")

    logging.info(f" Scraping complete! Crawled {len(visited_urls)} pages.")

if __name__ == "__main__":
    asyncio.run(main())