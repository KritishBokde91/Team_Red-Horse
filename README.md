# Credence — AI-Powered Misinformation Detection System

> **Credence** is an end-to-end, agentic fact-checking platform that verifies claims in real-time using a 6-stage AI pipeline. It combines multi-tier web scraping, stance detection via local LLMs, and a weighted consensus engine — all streamed live to a Flutter mobile app built with MVVM Clean Architecture.

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [The Fact-Checking Pipeline](#the-fact-checking-pipeline)
   - [Stage 1: Claim Extraction](#stage-1-claim-extraction)
   - [Stage 2: Multi-Tier Search](#stage-2-multi-tier-search)
   - [Stage 3: Evidence Scraping](#stage-3-evidence-scraping)
   - [Stage 4: Stance Detection](#stage-4-stance-detection)
   - [Stage 5: Verdict Computation](#stage-5-verdict-computation)
   - [Stage 6: Explanation Generation](#stage-6-explanation-generation)
3. [Key Technologies & Terms](#key-technologies--terms)
4. [Backend Architecture](#backend-architecture)
5. [Flutter App Architecture](#flutter-app-architecture)
6. [Configuration Reference](#configuration-reference)
7. [Setup & Running](#setup--running)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Flutter Mobile App                           │
│     ┌─────────┐   ┌──────────┐   ┌───────────┐   ┌──────────────┐ │
│     │ ClaimIn  │   │ Stepper  │   │ Evidence  │   │  Verdict     │ │
│     │ putCard  │   │ Widget   │   │ List      │   │  Card        │ │
│     └────┬─────┘   └─────▲────┘   └─────▲─────┘   └──────▲───────┘ │
│          │               │              │                │         │
│          ▼               │              │                │         │
│     ┌────────────────────┴──────────────┴────────────────┘         │
│     │                   VerifyBloc (BLoC)                          │
│     │              State Management Layer                          │
│     └───────────────────────┬─────────────────────────────         │
│                             │ SSE Stream                           │
│     ┌───────────────────────▼──────────────────────────┐           │
│     │            VerifyRemoteSource                     │           │
│     │         (HTTP SSE Client)                        │           │
│     └───────────────────────┬──────────────────────────┘           │
└─────────────────────────────┼──────────────────────────────────────┘
                              │ HTTP POST /verify
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend Server                           │
│                                                                     │
│  ┌──────────┐  ┌─────────────┐  ┌──────────┐  ┌────────────────┐  │
│  │  Claim   │→ │ Multi-Tier  │→ │ Evidence │→ │    Stance      │  │
│  │Extractor │  │   Search    │  │ Scraper  │  │   Detector     │  │
│  └──────────┘  └─────────────┘  └──────────┘  └───────┬────────┘  │
│                                                        │           │
│                                    ┌───────────────────▼────────┐  │
│                                    │  Verdict Engine            │  │
│                                    │  (Score + Explanation)     │  │
│                                    └───────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Ollama LLM Server                         │   │
│  │  ┌──────────────┐  ┌───────────────┐  ┌──────────────────┐  │   │
│  │  │ llama3.1:8b  │  │ snowflake-    │  │ bge-reranker-  │  │   │
│  │  │ (Judge)      │  │ arctic-embed2 │  │ v2-m3:f16      │  │   │
│  │  └──────────────┘  └───────────────┘  └──────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## The Fact-Checking Pipeline

When a user submits a claim like _"New Zealand Won 2026 T20 World Cup"_, the system executes a 6-stage agentic pipeline. Each stage streams real-time progress events via **Server-Sent Events (SSE)** to the mobile app.

### Stage 1: Claim Extraction

**File:** `claim_extractor.py`

**What it does:** Decomposes a user-submitted headline into **atomic, verifiable sub-claims**. A single headline may contain multiple factual assertions bundled together.

**How it works:**
1. The raw headline is sent to the **Judge LLM** (`llama3.1:8b`) with a structured prompt (`EXTRACTION_PROMPT`).
2. The LLM returns JSON containing:
   - **Atomic claims** — individual verifiable statements (e.g., _"New Zealand won the 2026 T20 World Cup"_).
   - **Entities** — people, organizations, and locations mentioned (e.g., `["New Zealand", "2026 T20 World Cup"]`).
   - **Search queries** — optimized queries for each claim designed for effective fact-checking (e.g., `"New Zealand 2026 T20 World Cup winner"`).
   - **Claim type** — classification into categories like `political`, `health`, `sports`, etc.
3. The response is sanitized using `_sanitize_llm_json()` to strip invalid backslash escapes that LLMs frequently produce.
4. Parsed using `json_repair` — a robust JSON parser that auto-fixes common LLM output issues (missing commas, extraneous text, malformed strings).

**Why it matters:** Without decomposition, complex claims would produce broad, unfocused search queries. Atomic decomposition ensures each verifiable fact gets its own targeted search, dramatically improving retrieval accuracy.

**Fallback:** If the LLM fails entirely, `_fallback_extraction()` treats the entire claim as one atomic claim, ensuring the pipeline never breaks.

---

### Stage 2: Multi-Tier Search

**File:** `fact_check_search.py`

**What it does:** Searches the internet for evidence using a **3-tier credibility hierarchy** of news sources. This is the core innovation that separates verified fact-checking from generic web search.

**The 3 Tiers:**

| Tier | Name | Credibility Weight | Sources | Purpose |
|------|------|-------------------|---------|---------|
| **T1** | Indian Fact-Checkers | **1.0** (highest) | AltNews, BoomLive, Factly, Vishvas News, PIB, TheQuint WebQoof, NewsChecker, etc. | IFCN-certified fact-checkers who have already investigated claims |
| **T2** | International Fact-Checkers | **0.85** | Snopes, PolitiFact, Reuters Fact Check, AFP, BBC Reality Check, FullFact, etc. | Global fact-checking organizations with rigorous editorial standards |
| **T3** | Mainstream News | **0.6** | The Hindu, Indian Express, NDTV, BBC, Reuters, AP News, ESPN Cricinfo, etc. | Trusted reporting that can corroborate or contradict claims |

**How it works:**
1. For each atomic claim's search query, the system performs **DuckDuckGo dorked searches**.
2. **Dorking** means restricting search results to specific domains by appending `site:domain.com` filters. For example:
   ```
   "New Zealand 2026 T20 World Cup winner" (site:altnews.in OR site:boomlive.in OR site:factly.in)
   ```
3. Results from each tier are tagged with their **credibility weight** — a numerical score from 0 to 1 that indicates how much the verdict engine trusts that source.
4. **URL deduplication** ensures the same article isn't counted multiple times across tiers.
5. Each result is streamed to the app in real-time (`tier_searching`, `tier_result`, `tier_complete` events).

**Why it matters:** Not all sources are equally trustworthy. A debunk article from AltNews (Tier 1, weight 1.0) has far more influence on the final verdict than a general news article from HindustanTimes (Tier 3, weight 0.6). This weighted approach prevents mainstream reporting noise from drowning out authoritative fact-checks.

**Why DuckDuckGo dorking instead of Google/APIs:** Zero third-party API dependencies. No API keys, no rate limits, no costs. The `ddgs` library provides programmatic search with site restriction, making the entire pipeline self-contained.

---

### Stage 3: Evidence Scraping

**File:** `search_scraper.py`

**What it does:** Fetches and extracts the actual text content from each URL found during search. Web pages are full of ads, navigation menus, and scripts — this module extracts only the meaningful article text.

**How it works (multi-tier scraping strategy):**

1. **Tier 1 — curl_cffi (fast):** Uses `curl_cffi` with browser impersonation to fetch pages quickly. This library mimics a real Chrome browser's TLS fingerprint, bypassing many anti-bot systems.

2. **Tier 2 — Trafilatura (smart extraction):** Once the raw HTML is fetched, `trafilatura` intelligently extracts the main article content. It uses a machine learning-based heuristic to identify the "main content" area, stripping away navigation, sidebars, ads, and other noise.

3. **Tier 3 — Selenium (fallback):** For JavaScript-heavy pages that return empty HTML on simple HTTP requests (e.g., some government sites like `pib.gov.in`), the system falls back to `undetected_chromedriver` — a headless Chrome browser that renders JavaScript and returns the fully-loaded page.

**Content processing:**
- `_clean_text()` collapses whitespace, removes artifacts, and normalizes the text.
- Content is truncated to prevent context window overflow in the LLM step.
- Each scraped page reports its character count to the frontend for transparency.

**Why it matters:** The pipeline can only classify stance on text it can actually read. Aggressive anti-bot protections on news sites (403 errors, CAPTCHA, JS rendering) would block naive HTTP requests. The multi-tier fallback ensures maximum content extraction across diverse websites.

---

### Stage 4: Stance Detection

**File:** `stance_detector.py`

**What it does:** For every scraped evidence article, classifies its **stance** relative to the original claim:
- **SUPPORTS** — The evidence confirms the claim is true.
- **REFUTES** — The evidence contradicts the claim.
- **NOT_ENOUGH_INFO** — The evidence is irrelevant or doesn't take a clear position.

**How it works:**

1. **Relevance Pre-Filter** (`_check_relevance()`):
   Before calling the LLM (which is expensive), a quick keyword-based check determines if the evidence likely discusses the claim at all. It extracts keywords from the claim and checks if a minimum percentage appear in the evidence text. Irrelevant articles are immediately classified as `NOT_ENOUGH_INFO` with low confidence, saving significant processing time.

2. **LLM Stance Classification** (`detect_stance()`):
   Relevant evidence is sent to the Judge LLM with `STANCE_PROMPT` — a carefully engineered prompt that includes:
   - The claim to verify.
   - The first 1500 characters of evidence text (truncated to prevent context overflow).
   - **Explicit instructions** to differentiate between "mentions the entities" and "actually supports the claim." This is critical — e.g., an article saying _"India defeated New Zealand in the T20 World Cup final"_ **REFUTES** (not supports) the claim _"New Zealand Won the T20 World Cup."_
   - Temperature set to `0.0` for deterministic, precise output.

3. **Robust JSON Parsing:**
   - `_sanitize_llm_json()` strips invalid backslash escape sequences.
   - `json_repair.loads()` auto-fixes common LLM JSON malformations.
   - **Defensive confidence parsing** using regex extracts numeric values even from hallucinated strings like `"0m"` (a real failure observed with the `phi3.5` model).

4. **Batch Processing** (`detect_stances_batch()`):
   Evidence items are processed sequentially with a semaphore (concurrency = 1) to avoid overloading the local Ollama server. Each result streams to the app immediately.

**Why it matters:** Stance detection is the most accuracy-critical stage. A single misclassification (e.g., labeling a refuting article as supporting) flips the entire verdict. The explicit prompt engineering around entity-vs-stance distinction and the relevance pre-filter work together to maximize classification accuracy while minimizing LLM calls.

---

### Stage 5: Verdict Computation

**File:** `verdict_engine.py`

**What it does:** Aggregates all stance classifications into a single **Veracity Score** and maps it to a human-readable verdict: **TRUE**, **FAKE**, or **UNVERIFIED**.

**The Scoring Algorithm:**

```
Veracity Score = Σ(stance_value × credibility_weight × stance_confidence) / Σ(credibility_weight × stance_confidence)
```

Where:
- `stance_value`: SUPPORTS = +1.0, REFUTES = −1.0, NOT_ENOUGH_INFO = 0.0
- `credibility_weight`: The tier-based trust score (1.0 for T1, 0.85 for T2, 0.6 for T3)
- `stance_confidence`: The LLM's self-reported confidence in its classification (0.0 to 1.0)

**Evidence Filtering:**
Evidence with `stance_confidence ≤ 0.1` is automatically excluded from scoring. These are typically irrelevant articles that passed the keyword filter but were classified as `NOT_ENOUGH_INFO` by the LLM with near-zero confidence. Including them would add noise and dilute the signal from definitive evidence.

**Verdict Mapping:**

| Veracity Score Range | Verdict | Meaning |
|---------------------|---------|---------|
| Score < **−0.3** | **FAKE** | Strong evidence contradicts the claim |
| Score > **+0.3** | **TRUE** | Strong evidence supports the claim |
| −0.3 ≤ Score ≤ +0.3 | **UNVERIFIED** | Insufficient or conflicting evidence |

An additional guard: if fewer than `MIN_EVIDENCE_COUNT` (default: 2) definitive stances are found, the verdict defaults to **UNVERIFIED** regardless of score — preventing strong conclusions from limited data.

**Confidence Calculation:**
- For FAKE/TRUE verdicts: Confidence = min(1.0, |veracity_score|)
- For UNVERIFIED: Confidence = 1.0 − |veracity_score| (closer to zero = more ambiguous)

**Why it matters:** The weighted consensus approach ensures that high-credibility sources (IFCN fact-checkers) have proportionally more influence than general news. A single AltNews article marking a claim as REFUTED carries the same weight as ~1.7 NDTV articles. This mirrors how fact-checking works in practice — specialist fact-checkers are more authoritative than general reporters.

---

### Stage 6: Explanation Generation

**File:** `verdict_engine.py` (function: `generate_explanation`)

**What it does:** Generates a 2-3 sentence human-readable explanation of **why** the claim received its verdict, citing specific sources.

**How it works:**
1. Builds an evidence summary containing only relevant stances (confidence > 0.1).
2. Sends a concise prompt to the Judge LLM with the claim, verdict, score, and evidence summary.
3. Temperature is set low (0.2) to keep the explanation factual and grounded.
4. `<think>` reasoning tags (from models like DeepSeek-R1) are stripped from the output.

**Fallback:** If the LLM fails, a template-based explanation is generated: _"The claim '...' has been rated as FAKE (score: -0.85). Analysis found 0 supporting source(s), 7 refuting source(s), and 2 inconclusive source(s)."_

**Why it matters:** A verdict without explanation is not actionable. Users need to understand *why* a claim is FAKE — which sources contradicted it, what the evidence says — to build trust in the system and make informed judgments.

---

## Key Technologies & Terms

### Ollama
An open-source tool for running Large Language Models (LLMs) locally on your machine. Unlike cloud-based APIs (OpenAI, Google), Ollama runs entirely on your hardware — **zero internet dependency, zero API costs, full privacy**. Credence uses Ollama to host 3 different models simultaneously.

### LLM (Large Language Model)
A neural network trained on vast text data that can understand and generate human language. Credence uses `llama3.1:8b` as its **Judge Model** — the "brain" that performs claim extraction, stance classification, and explanation generation. "8b" means 8 billion parameters, a good balance between intelligence and speed.

### Embeddings
Numerical vector representations of text. The sentence _"India won the cricket World Cup"_ gets converted into a list of ~1024 floating-point numbers. Sentences with similar meanings produce vectors that are mathematically **close** to each other in vector space. Credence uses `snowflake-arctic-embed2` for embedding.

### RAG (Retrieval-Augmented Generation)
A technique where the LLM is given relevant documents as context before generating a response. Instead of relying solely on its training data (which has a knowledge cutoff), the model retrieves fresh, relevant information and uses it to produce more accurate answers. Credence's RAG pipeline: Embed query → FAISS search → Rerank → LLM.

### FAISS (Facebook AI Similarity Search)
A library developed by Meta for efficient **similarity search** on high-dimensional vectors. When a user sends a message, FAISS finds the 15 most semantically similar past memories in milliseconds, even among millions of stored vectors.

### Reranking (BGE Reranker)
After FAISS retrieves 15 candidates, `bge-reranker-v2-m3` **re-scores** each one against the query for finer-grained relevance. FAISS is fast but approximate; the reranker is precise but slower. The combination (retrieve 15, rerank to 5) gives the best of both worlds.

### SSE (Server-Sent Events)
A web standard for streaming data from server to client over HTTP. Unlike WebSockets (which are bidirectional), SSE is unidirectional — the server pushes events to the client. Credence uses SSE to stream all 12 event types from the pipeline in real-time:
```
data: {"type": "stage", "stage": "claim_extraction", "message": "Extracting atomic claims..."}
data: {"type": "claims_extracted", "count": 1, "claims": [...]}
data: {"type": "tier_result", "tier": 1, "url": "...", "title": "..."}
...
data: {"type": "verdict", "verdict": "FAKE", "veracity_score": -0.85, ...}
data: [DONE]
```

### IFCN (International Fact-Checking Network)
A global alliance of fact-checking organizations that adhere to a verified set of principles: non-partisanship, transparency of sources, methodology, and corrections. Tier 1 domains in Credence are IFCN-certified or government-verified sources from India.

### DuckDuckGo Dorking
A search technique that restricts results to specific domains using `site:` operators. Example:
```
"Rahul Gandhi prime minister" (site:altnews.in OR site:boomlive.in)
```
This ensures the system searches **only** trusted fact-checking sources, not the entire internet (which would return noise, misinformation, and SEO spam).

### Stance Detection
The task of determining whether a piece of text **supports**, **refutes**, or is **neutral** toward a given claim. This is a supervised NLP classification task, but Credence uses an LLM with engineered prompts instead of a fine-tuned classifier — giving it flexibility to handle any topic without domain-specific training.

### Veracity Score
A number from **−1.0** (definitively false) to **+1.0** (definitively true), computed as the weighted average of all evidence stances. It is NOT a probability — it represents the **consensus direction** of evidence, weighted by source credibility and classification confidence.

### Neo-Brutalism (UI Design)
A modern design movement characterized by:
- **Thick black borders** (3-4px)
- **Solid offset drop shadows** (no blur, hard shadows at 4px offset)
- **Minimal color palette** (monochrome base with strategic accent colors)
- **No rounded corners** — intentionally flat and angular
- **Bold typography** — large, heavy fonts that demand attention

### BLoC (Business Logic Component)
A state management pattern for Flutter that separates business logic from UI. Events go in → States come out. The `VerifyBloc` receives a `SubmitClaim` event, processes the SSE stream, and emits incremental `VerifyState` updates that the UI reactively consumes.

### Clean Architecture (MVVM)
A software architecture that separates code into three layers:
- **Data Layer** — How data is fetched (HTTP, database, APIs)
- **Domain Layer** — Business rules (independent of frameworks/UI)
- **Presentation Layer** — UI and state management

This separation means you can swap the HTTP library, change the LLM provider, or redesign the entire UI without touching the other layers.

---

## Backend Architecture

### File Structure

```
backend/
├── main.py              # FastAPI server, SSE streaming, route handlers
├── config.py            # Centralized env config with typed constants
├── claim_extractor.py   # Stage 1: LLM-based atomic claim decomposition
├── fact_check_search.py # Stage 2: 3-tier DuckDuckGo dorked search
├── search_scraper.py    # Stage 3: Multi-method web scraping pipeline
├── stance_detector.py   # Stage 4: LLM stance classification with pre-filter
├── verdict_engine.py    # Stages 5-6: Weighted scoring + LLM explanation
├── rag_pipeline.py      # RAG: embedding → FAISS → reranking → context
├── vector_store.py      # FAISS/Chroma vector database abstraction
├── requirements.txt     # Python dependencies
└── .env                 # Environment configuration
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/verify` | POST | **Main fact-checking pipeline** — streams SSE events |
| `/chat` | POST | RAG-enhanced chat with streaming LLM response |
| `/web-search` | POST | Web search + scrape + RAG-augmented response |
| `/health` | GET | Server health check + Ollama connection status |
| `/models` | GET | List available Ollama chat models |

### Models Used

| Model | Size | Purpose | Why This Model |
|-------|------|---------|----------------|
| `llama3.1:8b` | 4.7 GB | Judge (extraction, stance, explanation) | Good balance of intelligence and speed; follows instructions well for JSON output |
| `snowflake-arctic-embed2` | 568 MB | Text embeddings for RAG | State-of-the-art embedding quality for retrieval tasks; multilingual support |
| `bge-reranker-v2-m3:f16` | 1.4 GB | Document reranking | Dramatically improves retrieval precision by re-scoring candidates |

---

## Flutter App Architecture

### File Structure

```
credence/lib/
├── main.dart                              # Entry point + BlocProvider wiring
├── core/
│   ├── constants.dart                     # API base URL (platform-aware)
│   └── theme.dart                         # Neo-brutalism theme system
├── data/
│   ├── models/
│   │   ├── sse_event_model.dart           # Typed SSE event wrapper
│   │   ├── evidence_model.dart            # Evidence item with stance data
│   │   └── verdict_model.dart             # Final verdict payload
│   ├── datasources/
│   │   └── verify_remote_source.dart      # SSE HTTP streaming client
│   └── repositories/
│       └── verify_repository_impl.dart    # Repository implementation
├── domain/
│   ├── repositories/
│   │   └── verify_repository.dart         # Abstract repository interface
│   └── usecases/
│       └── verify_claim_usecase.dart       # Use case orchestrator
└── presentation/
    ├── bloc/
    │   ├── verify_bloc.dart               # BLoC with 12 SSE event handlers
    │   ├── verify_event.dart              # SubmitClaim, ResetPipeline
    │   └── verify_state.dart              # Rich state with PipelineStage enum
    ├── screens/
    │   └── verify_screen.dart             # Main screen with progressive reveal
    └── widgets/
        ├── claim_input_card.dart           # Text input + submit button
        ├── pipeline_stepper.dart           # Animated 6-stage progress
        ├── evidence_list.dart              # Live evidence cards with status
        ├── stance_chart.dart               # Supports vs Refutes bar chart
        └── verdict_card.dart               # Final verdict display
```

### Data Flow

```
User types claim → SubmitClaim event → VerifyBloc
    → VerifyClaimUseCase → VerifyRepositoryImpl → VerifyRemoteSource
    → HTTP POST /verify → Backend Pipeline (6 stages)
    → SSE stream ← parse events ← update VerifyState
    → BlocBuilder rebuilds UI progressively
```

### Packages Used

| Package | Version | Purpose |
|---------|---------|---------|
| `flutter_bloc` | ^9.1.1 | BLoC state management pattern |
| `http` | ^1.4.0 | HTTP client for SSE byte streaming |
| `google_fonts` | ^6.2.0 | Space Grotesk + Inter typography |
| `flutter_spinkit` | ^5.2.1 | Loading animations (ThreeBounce, Pulse) |
| `shimmer` | ^3.0.0 | Skeleton loading for pending stances |
| `equatable` | ^2.0.7 | Value equality for BLoC states |

---

## Configuration Reference

### `.env` File

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `JUDGE_MODEL` | `llama3.1:8b` | LLM for claim extraction, stance, explanations |
| `EMBED_MODEL` | `snowflake-arctic-embed2:latest` | Embedding model for RAG |
| `RERANK_MODEL` | `qllama/bge-reranker-v2-m3:f16` | Reranker for RAG retrieval |
| `TIER1_WEIGHT` | `1.0` | Credibility weight for fact-checkers |
| `TIER2_WEIGHT` | `0.85` | Credibility weight for international sources |
| `TIER3_WEIGHT` | `0.6` | Credibility weight for mainstream news |
| `VERDICT_FAKE_THRESHOLD` | `-0.3` | Score below this → FAKE |
| `VERDICT_TRUE_THRESHOLD` | `0.3` | Score above this → TRUE |
| `MIN_EVIDENCE_COUNT` | `2` | Minimum definitive stances needed for verdict |
| `FACT_CHECK_RESULTS_PER_TIER` | `5` | Max results fetched per search tier |

---

## Setup & Running

### Prerequisites

- **Python 3.11+** with pip
- **Flutter 3.x** SDK
- **Ollama** installed and running
- Chrome/Chromium (for Selenium fallback scraping)

### Backend

```bash
# 1. Install dependencies
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Pull required Ollama models
ollama pull llama3.1:8b
ollama pull snowflake-arctic-embed2:latest
ollama pull qllama/bge-reranker-v2-m3:f16

# 3. Start the server
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

### Flutter App

```bash
# 1. Install dependencies
cd credence
flutter pub get

# 2. Update API URL in lib/core/constants.dart
# Set to your backend's IP address

# 3. Run on device/emulator
flutter run --release
```

### Testing with curl

```bash
curl -N -X POST http://localhost:8080/verify \
  -H "Content-Type: application/json" \
  -d '{"claim": "Rahul Gandhi is the current Prime Minister of India"}'
```

---

## License

This project was built for the Hackatronix hackathon.
