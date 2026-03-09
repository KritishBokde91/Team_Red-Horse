"""
claim_extractor.py - Extracts atomic claims from user-submitted headlines.
Uses deepseek-r1 to decompose a headline into structured, verifiable sub-claims.
"""
from __future__ import annotations
import json
import json_repair
import re
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
                # Invalid escape: drop the backslash, keep the character
                result.append(next_char)
                i += 2
        else:
            result.append(raw_json[i])
            i += 1
    return ''.join(result)


EXTRACTION_PROMPT = """You are a fact-checking analyst. Your job is to decompose a news headline or claim into its atomic, verifiable sub-claims.

RULES:
1. Extract ONLY factual assertions that can be verified (not opinions).
2. Each atomic claim should be a single, self-contained statement.
3. Preserve names, dates, locations, and numbers exactly as stated.
4. Generate optimized search queries for each claim that a fact-checker would use.
5. Respond ONLY with valid JSON, no other text.

INPUT CLAIM: "{claim}"

Respond with this exact JSON structure:
{{
  "original_claim": "<the original claim>",
  "language_detected": "<en/hi/hinglish/other>",
  "atomic_claims": [
    {{
      "claim_text": "<single verifiable statement>",
      "entities": ["<person>", "<org>", "<location>"],
      "search_query": "<optimized search query for fact-checking this claim>"
    }}
  ],
  "claim_type": "<political/health/science/disaster/social/financial/other>",
  "urgency": "<high/medium/low>"
}}"""


async def extract_claims(claim: str) -> Dict[str, Any]:
    """
    Decompose a user-submitted headline into atomic, verifiable claims.
    Uses the judge model (deepseek-r1:14b) for structured extraction.

    Returns dict with keys: original_claim, language_detected, atomic_claims,
    claim_type, urgency
    """
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": JUDGE_MODEL,
                    "prompt": EXTRACTION_PROMPT.format(claim=claim),
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_ctx": 4096,
                    },
                },
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "")

            # deepseek-r1 wraps reasoning in <think>...</think> tags
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

            sanitized = _sanitize_llm_json(raw)
            # Use json_repair to robustly parse broken JSON from smaller models
            parsed = json_repair.loads(sanitized)

            if not isinstance(parsed, dict):
                logger.warning(f"Parsed response is not a dictionary: {type(parsed)}")
                return _fallback_extraction(claim)

            # Validate required fields
            if "atomic_claims" not in parsed or not parsed["atomic_claims"]:
                logger.warning("No atomic_claims in parsed response, using fallback")
                return _fallback_extraction(claim)

            parsed["original_claim"] = claim
            logger.info(
                f"Extracted {len(parsed['atomic_claims'])} atomic claims "
                f"(type={parsed.get('claim_type', 'unknown')})"
            )
            return parsed

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in claim extraction: {e}")
        return _fallback_extraction(claim)
    except Exception as e:
        logger.error(f"Claim extraction failed: {e}")
        return _fallback_extraction(claim)


def _fallback_extraction(claim: str) -> Dict[str, Any]:
    """
    Fallback when LLM extraction fails.
    Treats the entire claim as a single atomic claim.
    """
    return {
        "original_claim": claim,
        "language_detected": "en",
        "atomic_claims": [
            {
                "claim_text": claim,
                "entities": [],
                "search_query": claim,
            }
        ],
        "claim_type": "other",
        "urgency": "medium",
    }
