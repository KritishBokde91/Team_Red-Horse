"""
stance_detector.py - Per-evidence stance classification.

For every scraped evidence snippet, uses the judge model to classify its
stance relative to the original claim:
  SUPPORTS | REFUTES | NOT_ENOUGH_INFO

Includes relevance pre-filtering to skip unrelated articles before LLM call.
"""
from __future__ import annotations
import json
import json_repair
import re
import asyncio
import httpx
from typing import List, Dict, Any
from loguru import logger
from config import OLLAMA_BASE_URL, JUDGE_MODEL


def _sanitize_llm_json(raw_json: str) -> str:
    """Sanitize LLM JSON output by removing invalid backslash escape sequences."""
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


def _check_relevance(claim: str, evidence_text: str, snippet: str) -> bool:
    """
    Quick keyword-based relevance check before calling the LLM.
    Returns True if evidence is likely relevant to the claim.
    """
    claim_lower = claim.lower()
    combined_text = (evidence_text[:1000] + " " + snippet).lower()

    # Extract significant words from claim (3+ chars, skip stopwords)
    stopwords = {"the", "was", "won", "has", "had", "are", "for", "and", "not",
                 "but", "this", "that", "with", "from", "will", "been", "have",
                 "just", "new", "old", "did", "does", "who", "what", "when"}
    claim_words = [w for w in re.findall(r'[a-z0-9]+', claim_lower)
                   if len(w) >= 3 and w not in stopwords]

    if not claim_words:
        return True  # Can't filter, let LLM decide

    # Require at least 30% of claim keywords to be present
    matches = sum(1 for w in claim_words if w in combined_text)
    ratio = matches / len(claim_words)
    return ratio >= 0.3


STANCE_PROMPT = """You are a precise fact-checking analyst. Your task is to determine whether the EVIDENCE supports or contradicts the CLAIM.

CLAIM TO VERIFY: "{claim}"

EVIDENCE TEXT:
---
{evidence}
---

IMPORTANT INSTRUCTIONS:
- Read the evidence CAREFULLY. Focus on WHAT ACTUALLY HAPPENED according to the evidence.
- SUPPORTS means the evidence confirms the claim is TRUE.
- REFUTES means the evidence shows the claim is FALSE or contradicts it.
- NOT_ENOUGH_INFO means the evidence is unrelated or does not address the claim.

EXAMPLE: If the claim is "Team X won the championship" but the evidence says "Team Y defeated Team X in the final", that REFUTES the claim because Team X LOST.

Respond with ONLY this JSON:
{{"stance": "SUPPORTS or REFUTES or NOT_ENOUGH_INFO", "confidence": 0.9, "reasoning": "one sentence why"}}"""


async def detect_stance(
    claim: str,
    evidence_text: str,
    source_url: str,
    snippet: str = "",
) -> Dict[str, Any]:
    """
    Classify the stance of a single evidence passage relative to the claim.
    """
    # Skip very short evidence
    if len(evidence_text.strip()) < 50:
        return {
            "stance": "NOT_ENOUGH_INFO",
            "confidence": 0.1,
            "key_phrases": [],
            "reasoning": "Evidence too short to analyze",
        }

    # Relevance pre-filter: skip unrelated articles
    if not _check_relevance(claim, evidence_text, snippet):
        logger.info(f"Skipping irrelevant evidence: {source_url}")
        return {
            "stance": "NOT_ENOUGH_INFO",
            "confidence": 0.1,
            "key_phrases": [],
            "reasoning": "Evidence not relevant to the claim",
        }

    # Truncate evidence to fit context window (use less text for speed)
    truncated_evidence = evidence_text[:2000]

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": JUDGE_MODEL,
                    "prompt": STANCE_PROMPT.format(
                        claim=claim,
                        evidence=truncated_evidence,
                    ),
                    "stream": False,
                    "options": {
                        "temperature": 0.0,
                        "num_ctx": 3072,
                    },
                },
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "")

            # Strip <think> tags if present (deepseek-r1)
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

            sanitized = _sanitize_llm_json(raw)
            # Use json_repair to robustly parse broken JSON from smaller models
            parsed = json_repair.loads(sanitized)

            if not isinstance(parsed, dict):
                logger.warning(f"Parsed response is not a dictionary: {type(parsed)}")
                return _fallback_stance()

            # Validate stance value
            valid_stances = {"SUPPORTS", "REFUTES", "NOT_ENOUGH_INFO"}
            if parsed.get("stance") not in valid_stances:
                parsed["stance"] = "NOT_ENOUGH_INFO"

            # Safely parse confidence (LLMs sometimes hallucinate strings like "0m")
            try:
                raw_conf = parsed.get("confidence", 0.5)
                # Handle cases where it's a string with extra characters
                if isinstance(raw_conf, str):
                    # Extract just the numbers and decimal point
                    match = re.search(r"(\d+(\.\d+)?)", raw_conf)
                    if match:
                        conf_val = float(match.group(1))
                    else:
                        conf_val = 0.5
                else:
                    conf_val = float(raw_conf)
            except (ValueError, TypeError):
                conf_val = 0.5

            # Clamp confidence
            parsed["confidence"] = max(0.0, min(1.0, conf_val))

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
    Run stance detection on a batch of evidence items.
    Processes sequentially (1 at a time) to avoid overloading Ollama with a small model.
    """
    # Process one at a time so the small model doesn't get overwhelmed
    semaphore = asyncio.Semaphore(1)

    async def _detect_with_semaphore(evidence: Dict[str, Any]) -> Dict[str, Any]:
        async with semaphore:
            stance = await detect_stance(
                claim=claim,
                evidence_text=evidence.get("content", ""),
                source_url=evidence.get("url", ""),
                snippet=evidence.get("snippet", ""),
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
