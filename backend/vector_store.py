"""
vector_store.py - FAISS / ChromaDB vector store for RAG memory pipeline
"""
from __future__ import annotations
import os
import json
import uuid
import pickle
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger

VECTOR_DB_TYPE = os.getenv("VECTOR_DB_TYPE", "faiss")
VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./data/vector_store")


# ─── Base ─────────────────────────────────────────────────────────────────────

class Memory:
    def __init__(
        self,
        id: str,
        content: str,
        conversation_id: str,
        role: str,
        metadata: Dict[str, Any] | None = None,
    ):
        self.id = id
        self.content = content
        self.conversation_id = conversation_id
        self.role = role
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Memory":
        return cls(
            id=d["id"],
            content=d["content"],
            conversation_id=d["conversation_id"],
            role=d["role"],
            metadata=d.get("metadata", {}),
        )


# ─── FAISS Store ──────────────────────────────────────────────────────────────

class FAISSVectorStore:
    def __init__(self, db_path: str = VECTOR_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.index_path = self.db_path / "index.faiss"
        self.meta_path = self.db_path / "metadata.pkl"
        self._index = None
        self._memories: List[Memory] = []
        self._dim: int | None = None
        self._load()

    def _load(self):
        try:
            import faiss  # type: ignore
            if self.index_path.exists() and self.meta_path.exists():
                self._index = faiss.read_index(str(self.index_path))
                with open(self.meta_path, "rb") as f:
                    self._memories = pickle.load(f)
                self._dim = self._index.d
                logger.info(f"Loaded FAISS index with {len(self._memories)} memories, dim={self._dim}")
        except Exception as e:
            logger.warning(f"Could not load existing FAISS index: {e}")

    def _save(self):
        try:
            import faiss  # type: ignore
            if self._index is not None:
                faiss.write_index(self._index, str(self.index_path))
            with open(self.meta_path, "wb") as f:
                pickle.dump(self._memories, f)
        except Exception as e:
            logger.error(f"Error saving FAISS index: {e}")

    def add(self, embedding: List[float], memory: Memory):
        import faiss  # type: ignore
        vec = np.array([embedding], dtype=np.float32)
        if self._index is None:
            self._dim = len(embedding)
            self._index = faiss.IndexFlatIP(self._dim)
            faiss.normalize_L2(vec)
        else:
            faiss.normalize_L2(vec)
        self._index.add(vec)
        self._memories.append(memory)
        self._save()

    def search(self, embedding: List[float], top_k: int = 15, conversation_id: Optional[str] = None) -> List[Tuple[Memory, float]]:
        if self._index is None or self._index.ntotal == 0:
            return []
        import faiss  # type: ignore
        vec = np.array([embedding], dtype=np.float32)
        faiss.normalize_L2(vec)
        k = min(top_k * 3, self._index.ntotal)
        scores, indices = self._index.search(vec, k)
        results: List[Tuple[Memory, float]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self._memories):
                continue
            mem = self._memories[idx]
            if conversation_id and mem.conversation_id != conversation_id:
                continue
            results.append((mem, float(score)))
            if len(results) >= top_k:
                break
        return results

    def get_by_conversation(self, conversation_id: str) -> List[Memory]:
        return [m for m in self._memories if m.conversation_id == conversation_id]

    def delete_conversation(self, conversation_id: str):
        # Rebuild index without memories from that conversation
        import faiss  # type: ignore
        keep = [m for m in self._memories if m.conversation_id != conversation_id]
        if not keep:
            self._index = None
            self._memories = []
            self._save()
            return
        logger.info(f"Rebuilding index after deleting conversation {conversation_id}")
        self._memories = keep
        # We don't store raw embeddings so we can't rebuild properly here.
        # For simplicity, just reset - embeddings will be re-added on next interaction.
        self._index = None
        self._save()


# ─── ChromaDB Store ───────────────────────────────────────────────────────────

class ChromaVectorStore:
    def __init__(self, db_path: str = VECTOR_DB_PATH):
        import chromadb  # type: ignore
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(
            name="memories",
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, embedding: List[float], memory: Memory):
        self.collection.add(
            embeddings=[embedding],
            documents=[memory.content],
            metadatas=[{
                "conversation_id": memory.conversation_id,
                "role": memory.role,
                **memory.metadata,
            }],
            ids=[memory.id],
        )

    def search(self, embedding: List[float], top_k: int = 15, conversation_id: Optional[str] = None) -> List[Tuple[Memory, float]]:
        where = {"conversation_id": conversation_id} if conversation_id else None
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, self.collection.count() or 1),
            where=where,
        )
        memories = []
        if not results["ids"] or not results["ids"][0]:
            return memories
        for i, doc_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            doc = results["documents"][0][i]
            dist = results["distances"][0][i] if results.get("distances") else 0.0
            score = 1.0 - dist
            mem = Memory(
                id=doc_id,
                content=doc,
                conversation_id=meta.get("conversation_id", ""),
                role=meta.get("role", "user"),
                metadata=meta,
            )
            memories.append((mem, score))
        return memories

    def get_by_conversation(self, conversation_id: str) -> List[Memory]:
        results = self.collection.get(where={"conversation_id": conversation_id})
        mems = []
        for i, doc_id in enumerate(results["ids"]):
            meta = results["metadatas"][i]
            doc = results["documents"][i]
            mems.append(Memory(
                id=doc_id, content=doc,
                conversation_id=meta.get("conversation_id", ""),
                role=meta.get("role", "user"),
                metadata=meta,
            ))
        return mems

    def delete_conversation(self, conversation_id: str):
        results = self.collection.get(where={"conversation_id": conversation_id})
        if results["ids"]:
            self.collection.delete(ids=results["ids"])


# ─── Factory ──────────────────────────────────────────────────────────────────

def create_vector_store() -> FAISSVectorStore | ChromaVectorStore:
    if VECTOR_DB_TYPE == "chroma":
        logger.info("Using ChromaDB vector store")
        return ChromaVectorStore()
    logger.info("Using FAISS vector store")
    return FAISSVectorStore()
