"""
rag_pipeline.py - Full RAG pipeline:
  snowflake-arctic-embed2 → FAISS/Chroma → Top 15 → bge-reranker → Top 5 → LLM
"""
from __future__ import annotations
import os
import uuid
import json
import httpx
from typing import List, Dict, Any, Tuple, Optional
from loguru import logger
from dotenv import load_dotenv
from vector_store import Memory, create_vector_store

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL     = os.getenv("EMBED_MODEL",   "snowflake-arctic-embed2:latest")
RERANK_MODEL    = os.getenv("RERANK_MODEL",  "qllama/bge-reranker-v2-m3:f16")
TOP_K_RETRIEVE  = int(os.getenv("TOP_K_RETRIEVE", "15"))
TOP_K_RERANK    = int(os.getenv("TOP_K_RERANK",   "5"))


class RAGPipeline:
    def __init__(self):
        self.store = create_vector_store()
        self.http = httpx.AsyncClient(timeout=120.0)

    # ── Embedding ─────────────────────────────────────────────────────────────
    async def embed(self, text: str) -> List[float]:
        try:
            r = await self.http.post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                json={"model": EMBED_MODEL, "prompt": text},
            )
            r.raise_for_status()
            return r.json()["embedding"]
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return []

    # ── Rerank via Ollama (prompt-based scoring) ──────────────────────────────
    async def rerank(self, query: str, docs: List[str], top_k: int = TOP_K_RERANK) -> List[int]:
        """
        Uses qllama/bge-reranker-v2-m3 to score each doc against the query.
        Returns indices of top_k docs sorted by relevance.
        """
        if not docs:
            return []
        scored: List[Tuple[int, float]] = []
        for i, doc in enumerate(docs):
            try:
                prompt = f"<query>{query}</query><passage>{doc}</passage>"
                r = await self.http.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": RERANK_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0},
                    },
                )
                r.raise_for_status()
                raw = r.json().get("response", "0").strip()
                # Parse first float from the response
                import re
                nums = re.findall(r"[-+]?\d*\.?\d+", raw)
                score = float(nums[0]) if nums else 0.0
                scored.append((i, score))
            except Exception as e:
                logger.warning(f"Rerank error for doc {i}: {e}")
                scored.append((i, 0.0))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [idx for idx, _ in scored[:top_k]]

    # ── Store a message in memory ─────────────────────────────────────────────
    async def store_memory(self, content: str, conversation_id: str, role: str):
        embedding = await self.embed(content)
        if not embedding:
            return
        mem = Memory(
            id=str(uuid.uuid4()),
            content=content,
            conversation_id=conversation_id,
            role=role,
        )
        self.store.add(embedding, mem)

    # ── Retrieve relevant context for a query ─────────────────────────────────
    async def retrieve_context(
        self,
        query: str,
        conversation_id: str,
        top_k_retrieve: int = TOP_K_RETRIEVE,
        top_k_rerank: int = TOP_K_RERANK,
    ) -> List[Dict[str, Any]]:
        """
        1. Embed query
        2. FAISS/Chroma → top 15 memories
        3. Rerank → top 5
        Returns list of memory dicts
        """
        embedding = await self.embed(query)
        if not embedding:
            return []

        # Step 1: Vector search → top 15
        candidates = self.store.search(
            embedding,
            top_k=top_k_retrieve,
            conversation_id=conversation_id,
        )
        if not candidates:
            return []

        docs = [m.content for m, _ in candidates]
        mems = [m for m, _ in candidates]

        # Step 2: Rerank → top 5
        top_indices = await self.rerank(query, docs, top_k=top_k_rerank)
        top_mems = [mems[i].to_dict() for i in top_indices]
        return top_mems

    # ── Build system prompt with context ─────────────────────────────────────
    def build_system_prompt(self, memories: List[Dict[str, Any]]) -> str:
        base = """You are Mercury AI — a powerful, highly capable, and versatile AI assistant.

CAPABILITIES:
- Answer questions accurately, logically, and conversationally on a wide range of topics
- Brainstorm ideas, draft creative writing, perform analysis, or summarize information
- You are also an elite software architect capable of writing production-ready code

WHEN WRITING CODE:
If the user specifically asks you to write or edit code, you must use the following artifact formats. (DO NOT use these formats for regular conversation!):

To generate new files:
### FILE: path/to/filename.ext
```language
// file content here
```
### END_FILE

To edit existing files accurately:
### EDIT: path/to/filename.ext
### FIND:
```
exact code to find (unique snippet)
```
### REPLACE:
```
new code to replace with
```
### END_EDIT"""

        if memories:
            context = "\n\n--- RELEVANT CONTEXT FROM MEMORY ---\n"
            for m in memories:
                role = m.get("role", "user").upper()
                context += f"[{role}]: {m.get('content', '')}\n"
            context += "--- END CONTEXT ---"
            return base + context
        return base

    # ── Build system prompt with web search context ───────────────────────────
    def build_web_search_prompt(
        self,
        web_context: str,
        sources: List[Dict[str, Any]],
        memories: List[Dict[str, Any]] | None = None,
    ) -> str:
        base = """You are Mercury AI — a powerful, highly capable, and versatile AI assistant with real-time web access.

You have just searched the web and retrieved the following information. Use it to provide an accurate, up-to-date answer.

IMPORTANT RULES:
- Base your answer primarily on the web search results provided below
- Cite sources when referencing specific information using [Source: title](url) format
- If the web results don't fully answer the question, say so clearly
- Combine web results with your own knowledge when appropriate
- Be concise, helpful, and directly answer the question
- Answer conversationally, and do not use code-editing artifact structures unless explicitly asked to modify code"""

        # Add web context
        if web_context:
            base += f"\n\n--- WEB SEARCH RESULTS ---\n{web_context}\n--- END WEB RESULTS ---"

        # Add source list
        if sources:
            base += "\n\nSOURCES USED:\n"
            for i, s in enumerate(sources, 1):
                base += f"{i}. [{s.get('title', 'Untitled')}]({s.get('url', '')})\n"

        # Add RAG memory context if available
        if memories:
            context = "\n\n--- RELEVANT CONTEXT FROM MEMORY ---\n"
            for m in memories:
                role = m.get("role", "user").upper()
                context += f"[{role}]: {m.get('content', '')}\n"
            context += "--- END CONTEXT ---"
            base += context

        return base

    async def close(self):
        await self.http.aclose()


# Singleton
_pipeline: RAGPipeline | None = None

def get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline
