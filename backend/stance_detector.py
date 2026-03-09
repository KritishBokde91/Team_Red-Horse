"""
stance_detector.py - Per-evidence stance classification.

For every scraped evidence snippet, uses the judge model (deepseek-r1:14b)
to classify its stance relative to the original claim:
  SUPPORTS | REFUTES | NOT_ENOUGH_INFO

Returns structured stance objects with reasoning.
"""
from __future__ import annotations
import json
import re
import asyncio
import httpx
from typing import List, Dict, Any
from loguru import logger
from config import OLLAMA_BASE_URL, JUDGE_MODEL


def _sanitize_llm_json(raw_json: str) -> str:
    """Sanitize LLM JSON output by removing invalid backslash escape sequences."""
    # LLMs produce invalid escapes like backslash-e, backslash-s, backslash-a
    # We keep only valid JSON escapes and strip the backslash from invalid ones
    valid_escapes = set('"\\bfnrtu/')
    result = []
    i = 0
    while i < len(raw_json):
        if raw_json[i] == '\\' and i + 1 < len(raw_json):
            next_char = raw_json[i + 1]
            if next_char in valid_escapes:
                result.append(raw_json[i])
                result.append(next_char)
                i += 2
            else:
                result.append(next_char)
                i += 2
        else:
            result.append(raw_json[i])
            i += 1
    return ''.join(result)


STANCE_PROMPT = """You are an expert fact-checking analyst. Given a CLAIM and an EVIDENCE passage, determine the stance of the evidence relative to the claim.

CLAIM: "{claim}"

EVIDENCE (from {source_url}):
\"\"\"{evidence}\"\"\"

TASK:
1. Analyze whether the evidence SUPPORTS, REFUTES, or provides NOT_ENOUGH_INFO about the claim.
2. Identify the key phrases in the evidence that led to your conclusion.
3. Rate your confidence from 0.0 to 1.0.

Respond ONLY with valid JSON:
{{
  "stance": "SUPPORTS" | "REFUTES" | "NOT_ENOUGH_INFO",
  "confidence": <0.0-1.0>,
  "key_phrases": ["<phrase1>", "<phrase2>"],
  "reasoning": "<one-line explanation of why this evidence supports/refutes/is insufficient>"
}}"""


async def detect_stance(
    claim: str,
    evidence_text: str,
    source_url: str,
) -> Dict[str, Any]:
    """
    Classify the stance of a single evidence passage relative to the claim.

    Returns dict with keys: stance, confidence, key_phrases, reasoning
    """
    # Skip very short evidence
    if len(evidence_text.strip()) < 50:
        return {
            "stance": "NOT_ENOUGH_INFO",
            "confidence": 0.1,
            "key_phrases": [],
            "reasoning": "Evidence too short to analyze",
        }

    # Truncate very long evidence to fit context window
    truncated_evidence = evidence_text[:3000]

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": JUDGE_MODEL,
                    "prompt": STANCE_PROMPT.format(
                        claim=claim,
                        evidence=truncated_evidence,
                        source_url=source_url,
                    ),
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_ctx": 4096,
                    },
                },
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "")

            # Strip <think> tags from deepseek-r1
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

            # Extract JSON
            json_match = re.search(r"\{[\s\S]*\}", raw)
            if not json_match:
                logger.warning(f"No JSON in stance response for {source_url}")
                return _fallback_stance()

            sanitized = _sanitize_llm_json(json_match.group())
            parsed = json.loads(sanitized)

            # Validate stance value
            valid_stances = {"SUPPORTS", "REFUTES", "NOT_ENOUGH_INFO"}
            if parsed.get("stance") not in valid_stances:
                parsed["stance"] = "NOT_ENOUGH_INFO"

            # Clamp confidence
            parsed["confidence"] = max(0.0, min(1.0, float(parsed.get("confidence", 0.5))))

            return parsed

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in stance detection for {source_url}: {e}")
        return _fallback_stance()
    except Exception as e:
        logger.error(f"Stance detection failed for {source_url}: {e}")
        return _fallback_stance()


async def detect_stances_batch(
    claim: str,
    evidence_list: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Run stance detection on a batch of evidence items concurrently.
    Each item in evidence_list should have: url, title, content, tier, credibility_weight

    Returns list of evidence items enriched with stance data.
    """
    # Run up to 3 concurrently to avoid overloading Ollama
    semaphore = asyncio.Semaphore(3)

    async def _detect_with_semaphore(evidence: Dict[str, Any]) -> Dict[str, Any]:
        async with semaphore:
            stance = await detect_stance(
                claim=claim,
                evidence_text=evidence.get("content", ""),
                source_url=evidence.get("url", ""),
            )
            return {
                **evidence,
                "stance": stance["stance"],
                "stance_confidence": stance["confidence"],
                "key_phrases": stance.get("key_phrases", []),
                "stance_reasoning": stance.get("reasoning", ""),
            }

    tasks = [_detect_with_semaphore(ev) for ev in evidence_list]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    enriched = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Stance detection task failed: {result}")
            enriched.append({
                **evidence_list[i],
                "stance": "NOT_ENOUGH_INFO",
                "stance_confidence": 0.0,
                "key_phrases": [],
                "stance_reasoning": f"Error: {str(result)}",
            })
        else:
            enriched.append(result)

    return enriched


def _fallback_stance() -> Dict[str, Any]:
    """Default stance when detection fails."""
    return {
        "stance": "NOT_ENOUGH_INFO",
        "confidence": 0.0,
        "key_phrases": [],
        "reasoning": "Stance detection failed",
    }
