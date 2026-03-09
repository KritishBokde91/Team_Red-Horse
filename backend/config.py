"""
config.py - Centralized configuration for the Fake News Detection pipeline.
All .env values parsed into typed Python constants.
"""
from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

# ─── OLLAMA ───────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# ─── MODELS ───────────────────────────────────────────────────────────────────
EMBED_MODEL = os.getenv("EMBED_MODEL", "snowflake-arctic-embed2:latest")
RERANK_MODEL = os.getenv("RERANK_MODEL", "qllama/bge-reranker-v2-m3:f16")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "deepseek-r1:14b")
DEFAULT_CHAT_MODEL = os.getenv("DEFAULT_CHAT_MODEL", "vicuna:13b")
AVAILABLE_MODELS = os.getenv("AVAILABLE_MODELS", "vicuna:13b").split(",")

# ─── RAG PIPELINE ─────────────────────────────────────────────────────────────
TOP_K_RETRIEVE = int(os.getenv("TOP_K_RETRIEVE", "15"))
TOP_K_RERANK = int(os.getenv("TOP_K_RERANK", "5"))
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "8000"))

# ─── BACKEND ──────────────────────────────────────────────────────────────────
BACKEND_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8080"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
APP_NAME = os.getenv("APP_NAME", "NexusAI")

# ─── VECTOR DB ────────────────────────────────────────────────────────────────
VECTOR_DB_TYPE = os.getenv("VECTOR_DB_TYPE", "faiss")
VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./data/vector_store")

# ─── SELENIUM / SCRAPER ──────────────────────────────────────────────────────
SELENIUM_HEADLESS = os.getenv("SELENIUM_HEADLESS", "true").lower() == "true"
SELENIUM_ENABLED = os.getenv("SELENIUM_ENABLED", "true").lower() == "true"

# ─── FACT-CHECK DOMAINS ──────────────────────────────────────────────────────
# Tier 1: IFCN-certified Indian fact-checkers (highest credibility)
TIER1_DOMAINS = [
    d.strip() for d in os.getenv(
        "TIER1_FACT_CHECK_DOMAINS",
        "altnews.in,boomlive.in,factly.in,vishvasnews.com,pib.gov.in,thequint.com/news/webqoof,newschecker.in,smythi.in,factchecker.in,newsmobile.in,thelogicalindian.com"
    ).split(",")
]

# Tier 2: International fact-checkers & government sources
TIER2_DOMAINS = [
    d.strip() for d in os.getenv(
        "TIER2_FACT_CHECK_DOMAINS",
        "snopes.com,politifact.com,reuters.com/fact-check,factcheck.org,fullfact.org,apnews.com/hub/ap-fact-check,bbc.com/news/reality_check,logicallyfacts.com,polygraph.info,afp.com"
    ).split(",")
]

# Tier 3: Gold-standard Indian mainstream news
TIER3_DOMAINS = [
    d.strip() for d in os.getenv(
        "TIER3_NEWS_DOMAINS",
        "thehindu.com,indianexpress.com,ndtv.com,ptinews.com,hindustantimes.com,livemint.com,timesofindia.indiatimes.com,thewire.in,scroll.in,newslaundry.com,economictimes.indiatimes.com,bbc.com,reuters.com,aljazeera.com,theguardian.com,cnn.com"
    ).split(",")
]

# Credibility weights per tier
TIER1_WEIGHT = float(os.getenv("TIER1_WEIGHT", "1.0"))
TIER2_WEIGHT = float(os.getenv("TIER2_WEIGHT", "0.85"))
TIER3_WEIGHT = float(os.getenv("TIER3_WEIGHT", "0.6"))

# ─── FACT-CHECK PIPELINE ─────────────────────────────────────────────────────
# Number of results to fetch per tier
FACT_CHECK_RESULTS_PER_TIER = int(os.getenv("FACT_CHECK_RESULTS_PER_TIER", "5"))

# Verdict thresholds
VERDICT_FAKE_THRESHOLD = float(os.getenv("VERDICT_FAKE_THRESHOLD", "-0.3"))
VERDICT_TRUE_THRESHOLD = float(os.getenv("VERDICT_TRUE_THRESHOLD", "0.3"))

# Minimum evidence required before rendering a verdict
MIN_EVIDENCE_COUNT = int(os.getenv("MIN_EVIDENCE_COUNT", "2"))
