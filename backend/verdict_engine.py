"""
verdict_engine.py - Weighted consensus engine + explanation generator.

Computes a Veracity Score from stance-classified evidence:
  Score = Σ(stance_weight × credibility_weight) / Σ(credibility_weight)

Maps score to verdict: FAKE (🔴), UNVERIFIED (🟡), TRUE (🟢)
Generates a human-readable explanation via LLM.
"""
from __future__ import annotations
import json
import re
import httpx
from typing import List, Dict, Any
from loguru import logger
from config import (
    OLLAMA_BASE_URL, JUDGE_MODEL,
    VERDICT_FAKE_THRESHOLD, VERDICT_TRUE_THRESHOLD,
    MIN_EVIDENCE_COUNT,
)

# Stance numeric mapping
STANCE_SCORES = {
    "SUPPORTS": 1.0,
    "REFUTES": -1.0,
    "NOT_ENOUGH_INFO": 0.0,
}

EXPLANATION_PROMPT = """You are a senior fact-checking editor. Based on the following evidence analysis, write a clear, concise verdict explanation for a general audience.

ORIGINAL CLAIM: "{claim}"

VERDICT: {verdict} (Veracity Score: {score:.2f})

EVIDENCE BREAKDOWN:
{evidence_summary}

TASK: Write a 3–5 sentence explanation that:
1. States the verdict clearly
2. Cites the most important sources by name
3. Explains WHY the claim is {verdict} based on the evidence
4. Mentions any conflicting evidence if applicable

Write the explanation directly, no JSON formatting needed. Be professional and neutral."""


def compute_veracity_score(evidence_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute weighted veracity score from stance-classified evidence.

    Returns dict with:
      veracity_score: float (-1.0 to 1.0)
      verdict: str (FAKE / UNVERIFIED / TRUE)
      confidence: float (0.0 to 1.0)
      sources_summary: {supports: int, refutes: int, neutral: int}
    """
    if not evidence_list:
        return {
            "veracity_score": 0.0,
            "verdict": "UNVERIFIED",
            "confidence": 0.0,
            "sources_summary": {"supports": 0, "refutes": 0, "neutral": 0},
        }

    total_weighted_score = 0.0
    total_weight = 0.0
    supports = 0
    refutes = 0
    neutral = 0

    for ev in evidence_list:
        stance = ev.get("stance", "NOT_ENOUGH_INFO")
        cred_weight = ev.get("credibility_weight", 0.5)
        stance_conf = ev.get("stance_confidence", 0.5)

        # Combined weight: source credibility × stance confidence
        combined_weight = cred_weight * stance_conf
        stance_score = STANCE_SCORES.get(stance, 0.0)

        total_weighted_score += stance_score * combined_weight
        total_weight += combined_weight

        if stance == "SUPPORTS":
            supports += 1
        elif stance == "REFUTES":
            refutes += 1
        else:
            neutral += 1

    # Calculate normalized score
    veracity_score = total_weighted_score / total_weight if total_weight > 0 else 0.0

    # Determine verdict
    evidence_count = supports + refutes  # only count definitive stances
    if evidence_count < MIN_EVIDENCE_COUNT:
        verdict = "UNVERIFIED"
        confidence = 0.3
    elif veracity_score < VERDICT_FAKE_THRESHOLD:
        verdict = "FAKE"
        confidence = min(1.0, abs(veracity_score))
    elif veracity_score > VERDICT_TRUE_THRESHOLD:
        verdict = "TRUE"
        confidence = min(1.0, abs(veracity_score))
    else:
        verdict = "UNVERIFIED"
        confidence = 1.0 - abs(veracity_score)

    return {
        "veracity_score": round(veracity_score, 4),
        "verdict": verdict,
        "confidence": round(confidence, 4),
        "sources_summary": {
            "supports": supports,
            "refutes": refutes,
            "neutral": neutral,
        },
    }


async def generate_explanation(
    claim: str,
    verdict_data: Dict[str, Any],
    evidence_list: List[Dict[str, Any]],
) -> str:
    """
    Generate a human-readable explanation of the verdict using the LLM.
    """
    # Build evidence summary for the prompt
    evidence_lines = []
    for i, ev in enumerate(evidence_list, 1):
        stance = ev.get("stance", "NOT_ENOUGH_INFO")
        tier = ev.get("tier", "?")
        title = ev.get("title", "Unknown")
        reasoning = ev.get("stance_reasoning", "")
        evidence_lines.append(
            f"  {i}. [{stance}] (Tier {tier}) {title}\n     Reasoning: {reasoning}"
        )

    evidence_summary = "\n".join(evidence_lines) if evidence_lines else "No evidence found."

    verdict = verdict_data.get("verdict", "UNVERIFIED")
    score = verdict_data.get("veracity_score", 0.0)

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": JUDGE_MODEL,
                    "prompt": EXPLANATION_PROMPT.format(
                        claim=claim,
                        verdict=verdict,
                        score=score,
                        evidence_summary=evidence_summary,
                    ),
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_ctx": 4096,
                    },
                },
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "")

            # Strip <think> tags from deepseek-r1
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
            return raw if raw else _fallback_explanation(claim, verdict_data)

    except Exception as e:
        logger.error(f"Explanation generation failed: {e}")
        return _fallback_explanation(claim, verdict_data)


def _fallback_explanation(claim: str, verdict_data: Dict[str, Any]) -> str:
    """Fallback explanation when LLM fails."""
    verdict = verdict_data.get("verdict", "UNVERIFIED")
    summary = verdict_data.get("sources_summary", {})
    score = verdict_data.get("veracity_score", 0.0)

    return (
        f"The claim \"{claim}\" has been rated as {verdict} "
        f"(score: {score:.2f}). "
        f"Analysis found {summary.get('supports', 0)} supporting source(s), "
        f"{summary.get('refutes', 0)} refuting source(s), and "
        f"{summary.get('neutral', 0)} inconclusive source(s)."
    )
