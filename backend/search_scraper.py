"""
search_scraper.py - Intelligent web search & scraping pipeline
DuckDuckGo search (ddgs) → multi-method scraping → content extraction → chunking
Streams real-time progress events via async generator
"""
from __future__ import annotations
import os
import re
import asyncio
from typing import List, Dict, Any, AsyncGenerator
from loguru import logger

# ─── Config from .env ────────────────────────────────────────────────────────
SELENIUM_HEADLESS = os.getenv("SELENIUM_HEADLESS", "true").lower() == "true"
SELENIUM_ENABLED = os.getenv("SELENIUM_ENABLED", "true").lower() == "true"

USER_AGENT = (
    "MercuryAIBot/1.0 (https://github.com; bot-contact@example.com) "
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
MIN_CONTENT_LENGTH = 200      # chars - below this, try fallback
MAX_CONTENT_PER_PAGE = 8000   # chars - truncate beyond this
CHUNK_SIZE = 1000             # chars per chunk for context
REQUEST_TIMEOUT = 15          # seconds per page


# ─── Search via DuckDuckGo (ddgs) ────────────────────────────────────────────

async def search_ddg(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """
    Search DuckDuckGo and return top results.
    Returns list of {"title": ..., "url": ..., "snippet": ...}
    """
    try:
        from ddgs import DDGS
        import time
        results = []

        def _search():
            # Try multiple times to handle random connection drops
            for attempt in range(3):
                try:
                    with DDGS() as ddgs:
                        for r in ddgs.text(query, max_results=num_results, backend="lite"):
                            results.append({
                                "title": r.get("title", ""),
                                "url": r.get("href", ""),
                                "snippet": r.get("body", ""),
                            })
                    if results:
                        break
                except Exception as e:
                    logger.warning(f"DDGS attempt {attempt+1} failed: {e}")
                    time.sleep(1)
            return results

        # Run in thread to avoid blocking the event loop
        return await asyncio.get_event_loop().run_in_executor(None, _search)
    except Exception as e:
        logger.error(f"DuckDuckGo search error: {e}")
        return []


# ─── Content Extraction ──────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    """Clean extracted text: collapse whitespace, strip junk"""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


async def _fetch_with_curl_cffi(url: str) -> str:
    """Tier 1: Fast lightweight fetch with curl_cffi for browser impersonation"""
    from curl_cffi import requests
    async with requests.AsyncSession(
        impersonate="chrome120",
        timeout=REQUEST_TIMEOUT,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.google.com/",
        },
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text


def _extract_with_trafilatura(html: str, url: str) -> str:
    """Tier 2: Intelligent content extraction using trafilatura"""
    import trafilatura
    result = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=True,
        include_links=False,
        favor_precision=False,
        favor_recall=True,
        deduplicate=True,
    )
    return result or ""


def _fetch_with_selenium(url: str) -> str:
    """Tier 3: Selenium fallback for JS-rendered pages
    Runs headless by default, configurable via SELENIUM_HEADLESS env var.
    Uses undetected_chromedriver to bypass advanced anti-bot defenses.
    """
    try:
        import undetected_chromedriver as uc
        import time

        options = uc.ChromeOptions()
        if SELENIUM_HEADLESS:
            options.add_argument("--headless=new")
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")
        options.add_argument(f"--user-agent={USER_AGENT}")
        options.add_argument("--window-size=1920,1080")
        options.page_load_strategy = 'eager' # Don't wait for all images/resources
        options.add_argument("--log-level=3")

        # Let undetected_chromedriver figure out the path automatically
        driver = uc.Chrome(options=options, headless=SELENIUM_HEADLESS)

        try:
            driver.set_page_load_timeout(15)
            try:
                driver.get(url)
                # Wait briefly for JS to execute if eager load finished
                time.sleep(2.0)
            except Exception as e:
                # If 'timed out receiving message from renderer' happens,
                # the page source often contains the text we need anyway!
                logger.warning(f"Selenium get() timed out or raised error: {e}")
            
            content = driver.page_source
            return content
        finally:
            driver.quit()

    except Exception as e:
        logger.warning(f"Selenium fallback failed for {url}: {e}")
        return ""


async def scrape_url(url: str) -> Dict[str, Any]:
    """
    Scrape a single URL using multi-tier approach:
      1. httpx fetch (fast)
      2. trafilatura extraction (smart content parsing)
      3. Selenium fallback if content too short (JS-heavy pages)
    Returns {"url": ..., "title": ..., "content": ..., "chars": int, "success": bool}
    """
    result = {"url": url, "title": "", "content": "", "chars": 0, "success": False}
    html = ""
    content = ""

    try:
        # Tier 1: Fast fetch with impersonation
        html = await _fetch_with_curl_cffi(url)

        # Extract title
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if title_match:
            result["title"] = _clean_text(title_match.group(1))[:200]

        # Tier 2: Trafilatura extraction
        content = _extract_with_trafilatura(html, url)
    except Exception as e:
        logger.warning(f"Fast fetch failed for {url} ({e}). Falling back to Selenium.")

    try:
        # Tier 3: If content too short or fetch failed, try Selenium
        if len(content) < MIN_CONTENT_LENGTH and SELENIUM_ENABLED:
            logger.info(f"Content too short ({len(content)} chars), trying Selenium for {url}")
            try:
                # Run Selenium in thread pool with a strict 30s timeout so it NEVER hangs the API
                loop = asyncio.get_event_loop()
                selenium_html = await asyncio.wait_for(
                    loop.run_in_executor(None, _fetch_with_selenium, url),
                    timeout=30.0
                )
                if selenium_html:
                    selenium_content = _extract_with_trafilatura(selenium_html, url)
                    if len(selenium_content) > len(content):
                        content = selenium_content
                        # Re-extract title if we got better HTML
                        title_match2 = re.search(
                            r'<title[^>]*>(.*?)</title>',
                            selenium_html,
                            re.IGNORECASE | re.DOTALL,
                        )
                        if title_match2:
                            result["title"] = _clean_text(title_match2.group(1))[:200]
            except Exception as e:
                logger.warning(f"Selenium not available: {e}")

        # Fallback: basic HTML tag stripping if still too short
        if len(content) < MIN_CONTENT_LENGTH and html:
            stripped = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            stripped = re.sub(r'<style[^>]*>.*?</style>', '', stripped, flags=re.DOTALL | re.IGNORECASE)
            stripped = re.sub(r'<[^>]+>', ' ', stripped)
            stripped = _clean_text(stripped)
            if len(stripped) > len(content):
                content = stripped

        content = _clean_text(content)[:MAX_CONTENT_PER_PAGE]
        result["content"] = content
        result["chars"] = len(content)
        result["success"] = len(content) >= 50

    except Exception as e:
        logger.error(f"Scrape error for {url}: {e}")
        result["content"] = f"Error: {str(e)}"

    return result


# ─── Chunking ─────────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
    """Split text into chunks, trying to break at sentence boundaries"""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end >= len(text):
            chunks.append(text[start:])
            break
        # Try to break at sentence boundary
        for sep in ['. ', '.\n', '! ', '? ', '\n\n', '\n', ' ']:
            pos = text.rfind(sep, start + chunk_size // 2, end)
            if pos > start:
                end = pos + len(sep)
                break
        chunks.append(text[start:end])
        start = end
    return [c.strip() for c in chunks if c.strip()]


# ─── Main Pipeline ────────────────────────────────────────────────────────────

async def search_and_scrape(
    query: str,
    num_results: int = 5,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Full search + scrape pipeline. Yields SSE-style event dicts:
      {"type": "searching", "query": "..."}
      {"type": "found", "urls": [...], "total": N}
      {"type": "scraping", "url": "...", "index": 1, "total": N}
      {"type": "scraped", "url": "...", "title": "...", "chars": N}
      {"type": "failed", "url": "...", "error": "..."}
      {"type": "summarizing"}
      {"type": "done", "sources": [...], "context": "..."}
    """
    # Step 1: Search
    yield {"type": "searching", "query": query}
    results = await search_ddg(query, num_results)

    if not results:
        yield {"type": "done", "sources": [], "context": "No search results found."}
        return

    urls = [r["url"] for r in results]
    yield {"type": "found", "urls": urls, "total": len(urls)}

    # Step 2: Scrape each URL
    scraped_pages = []
    sources = []

    for i, search_result in enumerate(results):
        url = search_result["url"]
        yield {"type": "scraping", "url": url, "index": i + 1, "total": len(results)}

        page = await scrape_url(url)

        if page["success"]:
            scraped_pages.append(page)
            sources.append({
                "url": url,
                "title": page["title"] or search_result["title"],
                "snippet": search_result["snippet"],
                "chars": page["chars"],
            })
            yield {
                "type": "scraped",
                "url": url,
                "title": page["title"] or search_result["title"],
                "chars": page["chars"],
            }
        else:
            yield {"type": "failed", "url": url, "error": "Insufficient content extracted"}

    # Step 3: Build context from scraped content
    yield {"type": "summarizing"}

    context_parts = []
    for page in scraped_pages:
        title = page["title"] or page["url"]
        context_parts.append(f"--- Source: {title} ({page['url']}) ---\n{page['content']}")

    full_context = "\n\n".join(context_parts)

    # Chunk if too long (keep total under 15000 chars)
    if len(full_context) > 15000:
        full_context = full_context[:15000] + "\n\n[Content truncated for context window]"

    yield {
        "type": "done",
        "sources": sources,
        "context": full_context,
    }
