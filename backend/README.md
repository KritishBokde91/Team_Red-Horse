# NexusAI — Agentic Fake News Detection Backend

A high-accuracy misinformation detection system powered by an **Agentic Fact-Checking Pipeline**. Uses local LLMs via Ollama, multi-tier evidence retrieval from trusted fact-checkers, per-evidence stance analysis, and weighted consensus verdicts.

## Architecture

```
User Claim
    │
    ▼
┌──────────────────────┐
│  Claim Extractor     │  deepseek-r1:14b decomposes headline into
│  (claim_extractor.py)│  atomic, verifiable sub-claims
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────────────────────┐
│  Multi-Tier Search (fact_check_search.py)             │
│                                                       │
│  Tier 1 (wt 1.0)  → IFCN Indian fact-checkers        │
│  Tier 2 (wt 0.85) → International fact-checkers       │
│  Tier 3 (wt 0.6)  → Gold-standard mainstream news     │
│                                                       │
│  All via DuckDuckGo dorking — zero third-party APIs   │
└──────────┬───────────────────────────────────────────┘
           │
           ▼
┌──────────────────────┐
│  Evidence Scraper    │  curl_cffi (TLS impersonation) +
│  (search_scraper.py) │  undetected-chromedriver (JS fallback)
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Stance Detector     │  deepseek-r1:14b classifies each evidence:
│  (stance_detector.py)│  SUPPORTS | REFUTES | NOT_ENOUGH_INFO
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Verdict Engine      │  Weighted consensus formula:
│  (verdict_engine.py) │  Score = Σ(stance × credibility × confidence) / Σ(weights)
│                      │
│                      │  Score < -0.3 → 🔴 FAKE
│                      │  -0.3 to 0.3 → 🟡 UNVERIFIED
│                      │  Score > 0.3  → 🟢 TRUE
│                      │
│                      │  + LLM-generated explanation with source citations
└──────────────────────┘
```

## Models Used

| Role | Model | Purpose |
|------|-------|---------|
| **Reasoning/Judge** | `deepseek-r1:14b` | Claim extraction, stance detection, explanation generation |
| **Embeddings** | `snowflake-arctic-embed2:latest` | Vector embeddings for RAG memory |
| **Reranker** | `qllama/bge-reranker-v2-m3:f16` | Relevance scoring for memory retrieval |

## File Structure

```
backend/
├── config.py              # Centralized .env configuration
├── main.py                # FastAPI server with all endpoints
├── claim_extractor.py     # Stage 1: Atomic claim decomposition
├── fact_check_search.py   # Stage 2: Multi-tier dorked search
├── search_scraper.py      # Stage 3: Anti-bot web scraping
├── stance_detector.py     # Stage 4: Per-evidence stance classification
├── verdict_engine.py      # Stage 5: Weighted verdict + explanation
├── rag_pipeline.py        # RAG memory pipeline (for /chat endpoint)
├── vector_store.py        # FAISS/ChromaDB vector stores
├── requirements.txt       # Python dependencies
├── test_verify.py         # End-to-end verification test
└── test_api.py            # Web search test
```

## API Endpoints

### `POST /verify` — Fact-Check a Claim
The primary fact-checking endpoint. Streams SSE progress events.

**Request:**
```json
{
  "claim": "PM Modi resigned today",
  "num_results_per_tier": 5
}
```

**Response (streamed SSE, final event):**
```json
{
  "type": "verdict",
  "claim": "PM Modi resigned today",
  "verdict": "FAKE",
  "veracity_score": -0.85,
  "confidence": 0.92,
  "explanation": "This claim is rated FAKE based on...",
  "sources_summary": { "supports": 0, "refutes": 4, "neutral": 1 },
  "evidence": [
    {
      "url": "https://altnews.in/...",
      "title": "...",
      "tier": 1,
      "credibility_weight": 1.0,
      "stance": "REFUTES",
      "stance_confidence": 0.95,
      "stance_reasoning": "Article explicitly debunks...",
      "key_phrases": ["false claim", "no resignation"]
    }
  ],
  "atomic_claims": [
    {
      "claim_text": "PM Modi resigned",
      "entities": ["PM Modi"],
      "search_query": "PM Modi resignation fact check"
    }
  ]
}
```

### `POST /web-search` — General Web Search + LLM
### `POST /chat` — RAG-Augmented Chat
### `GET /health` — Health Check
### `GET /models` — Available Ollama Models

## Setup

```bash
# 1. Create virtual environment
cd backend
python -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Ensure Ollama is running with required models
ollama pull deepseek-r1:14b
ollama pull snowflake-arctic-embed2:latest
ollama pull qllama/bge-reranker-v2-m3:f16

# 4. Configure .env (already pre-configured)

# 5. Start server
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

## Testing

```bash
# Run the fact-checking test
python test_verify.py

# Results saved to verify_output.txt
```

## Configuration (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `JUDGE_MODEL` | `deepseek-r1:14b` | LLM for reasoning tasks |
| `EMBED_MODEL` | `snowflake-arctic-embed2:latest` | Embedding model |
| `RERANK_MODEL` | `qllama/bge-reranker-v2-m3:f16` | Reranking model |
| `TIER1_FACT_CHECK_DOMAINS` | `altnews.in,...` | IFCN Indian fact-checkers |
| `TIER2_FACT_CHECK_DOMAINS` | `snopes.com,...` | International fact-checkers |
| `TIER3_NEWS_DOMAINS` | `thehindu.com,...` | Mainstream news |
| `TIER1_WEIGHT` | `1.0` | Credibility weight for Tier 1 |
| `TIER2_WEIGHT` | `0.85` | Credibility weight for Tier 2 |
| `TIER3_WEIGHT` | `0.6` | Credibility weight for Tier 3 |
| `VERDICT_FAKE_THRESHOLD` | `-0.3` | Score below this = FAKE |
| `VERDICT_TRUE_THRESHOLD` | `0.3` | Score above this = TRUE |
| `MIN_EVIDENCE_COUNT` | `2` | Minimum definitive sources before verdict |
| `FACT_CHECK_RESULTS_PER_TIER` | `5` | DDG results per tier |

## Technologies

- **FastAPI** — async API framework
- **Ollama** — local LLM inference
- **FAISS** — vector similarity search
- **DuckDuckGo** — web search (zero API keys)
- **curl_cffi** — TLS-impersonating HTTP client
- **undetected-chromedriver** — anti-bot browser automation
- **trafilatura** — intelligent HTML content extraction
