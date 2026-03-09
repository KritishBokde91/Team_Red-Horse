# NexusAI Backend Documentation

This folder contains the backend services for the NexusAI Fake News Detection platform.

## Key Features Implemented

### 1. Advanced Web Scraping Pipeline (`search_scraper.py`)
- **DuckDuckGo Search Integration**: Uses the `ddgs` library to find relevant articles.
- **Anti-Bot Circumvention**:
    - **Tier 1 (Fast Fetching)**: Uses `curl_cffi` to impersonate browser TLS and HTTP fingerprints, bypassing basic bot protection (like basic Cloudflare protection).
    - **Tier 2 (Intelligent Parsing)**: Uses `trafilatura` for smart HTML content extraction, ensuring clean article text free of menus/ads.
    - **Tier 3 (JS & Advanced Fallback)**: Uses `undetected-chromedriver` for Selenium. This headless browser patches drivers to bypass advanced bot mitigation tools (like Datadome or advanced Cloudflare) often found on top news sites. 
- **Scalability**: Capable of safely scraping 15-20 sites asynchronously using increased timeout limits. Returns live Server-Sent Events (SSE).

### 2. Retrieval-Augmented Generation (RAG) Pipeline (`rag_pipeline.py`)
- **Embedding Generation**: Uses Ollama with `snowflake-arctic-embed2` to generate vector embeddings from scraped/user text.
- **Vector Database**: Implements a highly scalable switchable vector store, currently configured to use `faiss-cpu`.
- **Intelligent Reranking**: Re-scores Top 15 vector results using `qllama/bge-reranker-v2-m3` to provide the top 5 most relevant context snippets to the LLM. 

### 3. API & Streaming (`main.py`)
- **FastAPI Server**: Provides high-performance async endpoints.
- **Streaming Endpoints**: Both the standard chat (`/chat`) and web search (`/web-search`) pipelines stream tokens and JSON events (SSE) back to the client in real time.
- **Conversation State Management**: Keeps track of `conversation_ids` through the vector store for multi-turn RAG memory. 

### 4. Utilities
- **Dependency Management**: Standardized via `requirements.txt`.
- **Environment**: Configuration via `.env`.
- **Testing**: Includes a `test_api.py` script that hits the `/web-search` API looking for 15 live URL results, validating all capabilities end-to-end, writing output to `output.txt`.

## How to Run
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```
