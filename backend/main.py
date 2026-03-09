"""
main.py - NexusAI Backend FastAPI Server
Handles RAG pipeline, memory management, and streaming LLM responses
"""
from __future__ import annotations
import os
import json
import uuid
import httpx
import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

from rag_pipeline import get_pipeline
from search_scraper import search_and_scrape

# ─── Config ───────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL  = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL    = os.getenv("DEFAULT_CHAT_MODEL", "deepseek-r1:14b")
BACKEND_HOST     = os.getenv("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT     = int(os.getenv("BACKEND_PORT", "8000"))
AVAILABLE_MODELS = os.getenv(
    "AVAILABLE_MODELS",
    "vicuna:13b"
).split(",")

app = FastAPI(title="NexusAI Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Pydantic Models ─────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    conversation_id: str
    model: Optional[str] = DEFAULT_MODEL
    messages: List[ChatMessage]
    stream: Optional[bool] = True
    use_rag: Optional[bool] = True

class ConversationDeleteRequest(BaseModel):
    conversation_id: str

class WebSearchRequest(BaseModel):
    query: str
    conversation_id: str
    model: Optional[str] = DEFAULT_MODEL
    messages: List[ChatMessage] = []
    num_results: Optional[int] = 5
    use_rag: Optional[bool] = True

class OllamaModelsResponse(BaseModel):
    models: List[str]

class HealthResponse(BaseModel):
    status: str
    ollama: str
    available_models: List[str]


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health_check():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            r.raise_for_status()
            models_data = r.json()
            ollama_models = [m["name"] for m in models_data.get("models", [])]
            return HealthResponse(
                status="ok",
                ollama="connected",
                available_models=ollama_models or AVAILABLE_MODELS,
            )
    except Exception as e:
        return HealthResponse(
            status="ok",
            ollama=f"error: {str(e)}",
            available_models=AVAILABLE_MODELS,
        )


@app.get("/models")
async def get_models():
    """Returns list of available Ollama models (excluding embedding/reranker models)"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            r.raise_for_status()
            models_data = r.json()
            embed_keywords = ["embed", "arctic", "bge", "reranker"]
            all_models = [m["name"] for m in models_data.get("models", [])]
            chat_models = [
                m for m in all_models
                if not any(kw in m.lower() for kw in embed_keywords)
            ]
            return {"models": chat_models or AVAILABLE_MODELS}
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        return {"models": AVAILABLE_MODELS}


# ─── Chat Streaming ───────────────────────────────────────────────────────────

async def stream_ollama(
    model: str,
    messages: List[Dict],
    system_prompt: str,
) -> AsyncGenerator[str, None]:
    """Stream response from Ollama chat API"""
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "stream": True,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9,
            "num_ctx": 8192,
        },
    }
    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get("done"):
                        yield f"data: [DONE]\n\n"
                        break
                    content = data.get("message", {}).get("content", "")
                    if content:
                        payload_data = json.dumps({"content": content})
                        yield f"data: {payload_data}\n\n"
                except json.JSONDecodeError:
                    continue


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Main chat endpoint with RAG pipeline:
    1. Store latest user message in vector DB
    2. Retrieve top-15 memories → rerank → top-5
    3. Build system prompt with context
    4. Stream LLM response
    5. Store assistant response in memory
    """
    pipeline = get_pipeline()

    # Get the last user message
    user_messages = [m for m in request.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="No user message found")
    
    last_user_msg = user_messages[-1].content

    # Store user message in memory
    if request.use_rag:
        await pipeline.store_memory(
            content=last_user_msg,
            conversation_id=request.conversation_id,
            role="user",
        )

    # Retrieve relevant context
    memories = []
    if request.use_rag:
        memories = await pipeline.retrieve_context(
            query=last_user_msg,
            conversation_id=request.conversation_id,
        )
        logger.info(f"Retrieved {len(memories)} relevant memories for context")

    # Build system prompt
    system_prompt = pipeline.build_system_prompt(memories)

    # Convert messages for Ollama
    ollama_messages = [{"role": m.role, "content": m.content} for m in request.messages]

    # Buffer for storing assistant response
    assistant_buffer = []

    async def response_generator():
        full_response = ""
        async for chunk in stream_ollama(
            model=request.model or DEFAULT_MODEL,
            messages=ollama_messages,
            system_prompt=system_prompt,
        ):
            full_response_chunk = ""
            if chunk.startswith("data: ") and chunk != "data: [DONE]\n\n":
                try:
                    data = json.loads(chunk[6:])
                    full_response_chunk = data.get("content", "")
                except Exception:
                    pass
            full_response += full_response_chunk
            yield chunk
        
        # Store assistant response in memory after streaming
        if full_response and request.use_rag:
            asyncio.create_task(
                pipeline.store_memory(
                    content=full_response,
                    conversation_id=request.conversation_id,
                    role="assistant",
                )
            )

    return StreamingResponse(
        response_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─── Memory Management ────────────────────────────────────────────────────────

@app.delete("/conversation/{conversation_id}")
async def delete_conversation(conversation_id: str):
    pipeline = get_pipeline()
    pipeline.store.delete_conversation(conversation_id)
    return {"status": "deleted", "conversation_id": conversation_id}


@app.get("/conversation/{conversation_id}/memories")
async def get_memories(conversation_id: str):
    pipeline = get_pipeline()
    memories = pipeline.store.get_by_conversation(conversation_id)
    return {"memories": [m.to_dict() for m in memories]}


# ─── Code Analysis ────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    code: str
    language: str
    model: Optional[str] = DEFAULT_MODEL

@app.post("/analyze")
async def analyze_code(request: AnalyzeRequest):
    """Ask the LLM to analyze code for errors and improvements"""
    pipeline = get_pipeline()
    
    prompt = f"""Analyze the following {request.language} code for:
1. Syntax errors
2. Logic errors  
3. Security vulnerabilities
4. Performance issues
5. Best practice violations

Code:
```{request.language}
{request.code}
```

Provide a structured analysis with:
- ERRORS: (list any errors found)
- WARNINGS: (potential issues)
- SUGGESTIONS: (improvements)
- FIXED_CODE: (if there are errors, provide corrected code using the FILE/EDIT format)"""

    async def gen():
        async for chunk in stream_ollama(
            model=request.model,
            messages=[{"role": "user", "content": prompt}],
            system_prompt=pipeline.build_system_prompt([]),
        ):
            yield chunk

    return StreamingResponse(gen(), media_type="text/event-stream")


# ─── Web Search ───────────────────────────────────────────────────────────────

@app.post("/web-search")
async def web_search(request: WebSearchRequest):
    """
    Web search + scrape pipeline with streaming:
    1. Search DuckDuckGo & scrape pages (stream progress events)
    2. Build web-augmented system prompt
    3. Stream LLM response with web context
    """
    pipeline = get_pipeline()

    async def response_generator():
        web_context = ""
        sources = []

        # Phase 1: Search & scrape with progress events
        async for event in search_and_scrape(request.query, request.num_results or 5):
            event_data = json.dumps(event)
            yield f"data: {event_data}\n\n"

            if event["type"] == "done":
                web_context = event.get("context", "")
                sources = event.get("sources", [])

        if not web_context:
            error_data = json.dumps({"content": "I couldn't find any relevant information from the web. Please try a different query."})
            yield f"data: {error_data}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Phase 2: Retrieve RAG memories if enabled
        memories = []
        if request.use_rag:
            memories = await pipeline.retrieve_context(
                query=request.query,
                conversation_id=request.conversation_id,
            )

        # Phase 3: Build web-augmented system prompt
        system_prompt = pipeline.build_web_search_prompt(web_context, sources, memories)

        # Build messages for LLM
        ollama_messages = [{"role": m.role, "content": m.content} for m in request.messages]
        if not ollama_messages or ollama_messages[-1].get("content") != request.query:
            ollama_messages.append({"role": "user", "content": request.query})

        # Phase 4: Stream LLM response
        full_response = ""
        async for chunk in stream_ollama(
            model=request.model or DEFAULT_MODEL,
            messages=ollama_messages,
            system_prompt=system_prompt,
        ):
            if chunk.startswith("data: ") and chunk != "data: [DONE]\n\n":
                try:
                    data = json.loads(chunk[6:])
                    full_response += data.get("content", "")
                except Exception:
                    pass
            yield chunk

        # Store in memory
        if full_response and request.use_rag:
            asyncio.create_task(
                pipeline.store_memory(
                    content=full_response,
                    conversation_id=request.conversation_id,
                    role="assistant",
                )
            )

    return StreamingResponse(
        response_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=BACKEND_HOST,
        port=BACKEND_PORT,
        reload=False,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )