"""
fact_check_search.py - Multi-tier search strategy for fact-checking.

Tier 1: IFCN-certified Indian fact-checkers (weight 1.0)
Tier 2: International fact-checkers (weight 0.85)
Tier 3: Gold-standard Indian mainstream news (weight 0.6)

All search is done via DuckDuckGo dorking — zero third-party API dependencies.
"""
from __future__ import annotations
import asyncio
from typing import List, Dict, Any, AsyncGenerator
from loguru import logger
from config import (
    TIER1_DOMAINS, TIER2_DOMAINS, TIER3_DOMAINS,
    TIER1_WEIGHT, TIER2_WEIGHT, TIER3_WEIGHT,
    FACT_CHECK_RESULTS_PER_TIER,
)


# ─── DuckDuckGo Dorked Search ────────────────────────────────────────────────

async def _search_ddg_dorked(
    query: str,
    domains: List[str],
    num_results: int = 5,
) -> List[Dict[str, str]]:
    """
    Search DuckDuckGo with site-restriction dorking.
    Constructs queries like: "claim text" site:altnews.in OR site:boomlive.in
    """
    from ddgs import DDGS
    import time

    # Build dorked query
    site_filter = " OR ".join(f"site:{d}" for d in domains)
    dorked_query = f"{query} ({site_filter})"

    results = []

    def _search():
        for attempt in range(3):
            try:
                with DDGS() as ddgs:
                    for r in ddgs.text(dorked_query, max_results=num_results, backend="lite"):
                        results.append({
                            "title": r.get("title", ""),
                            "url": r.get("href", ""),
                            "snippet": r.get("body", ""),
                        })
                if results:
                    break
            except Exception as e:
                logger.warning(f"DDGS dorked attempt {attempt+1} failed: {e}")
                time.sleep(1)
        return results

    try:
        return await asyncio.get_event_loop().run_in_executor(None, _search)
    except Exception as e:
        logger.error(f"Dorked search error: {e}")
        return []


# ─── Multi-Tier Search Pipeline ──────────────────────────────────────────────

async def multi_tier_search(
    search_queries: List[str],
    results_per_tier: int = FACT_CHECK_RESULTS_PER_TIER,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Execute multi-tier fact-check search across all queries.
    Yields SSE-style progress events and tagged results.

    Events:
      {"type": "tier_searching", "tier": 1, "query": "..."}
      {"type": "tier_result", "tier": 1, "url": "...", "title": "...", "weight": 1.0}
      {"type": "tier_complete", "tier": 1, "count": N}
      {"type": "search_done", "total_results": N}
    """
    all_results: List[Dict[str, Any]] = []
    seen_urls: set = set()

    tiers = [
        (1, TIER1_DOMAINS, TIER1_WEIGHT, "Indian Fact-Checkers"),
        (2, TIER2_DOMAINS, TIER2_WEIGHT, "International Fact-Checkers"),
        (3, TIER3_DOMAINS, TIER3_WEIGHT, "Mainstream News"),
    ]

    for tier_num, domains, weight, tier_name in tiers:
        tier_results = []

        for query in search_queries:
            yield {
                "type": "tier_searching",
                "tier": tier_num,
                "tier_name": tier_name,
                "query": query,
            }

            results = await _search_ddg_dorked(query, domains, results_per_tier)

            for r in results:
                url = r["url"]
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                tagged_result = {
                    **r,
                    "tier": tier_num,
                    "tier_name": tier_name,
                    "credibility_weight": weight,
                }
                tier_results.append(tagged_result)

                yield {
                    "type": "tier_result",
                    "tier": tier_num,
                    "url": url,
                    "title": r["title"],
                    "weight": weight,
                }

        all_results.extend(tier_results)
        yield {
            "type": "tier_complete",
            "tier": tier_num,
            "tier_name": tier_name,
            "count": len(tier_results),
        }

    yield {
        "type": "search_done",
        "total_results": len(all_results),
        "results": all_results,
    }
