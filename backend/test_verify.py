"""
test_verify.py - End-to-end test for the /verify fact-checking endpoint.
Streams SSE events and writes the full output to verify_output.txt.
"""
import json
import httpx
import asyncio

CLAIMS_TO_TEST = [
    # Known fake / misleading claim
    "NASA confirms asteroid will destroy Earth in 2025",
    # Known true claim
    "India's Chandrayaan-3 successfully landed on the Moon's south pole in August 2023",
]


async def test_verify(claim: str, output_file):
    url = "http://localhost:8080/verify"
    payload = {"claim": claim, "num_results_per_tier": 3}

    output_file.write(f"\n{'='*80}\n")
    output_file.write(f"CLAIM: {claim}\n")
    output_file.write(f"{'='*80}\n\n")

    print(f"\n{'='*60}")
    print(f"Testing claim: {claim}")
    print(f"{'='*60}")

    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    print(f"  Error: {response.status_code}")
                    return

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    if line.startswith("data: "):
                        data_str = line[6:]
                        output_file.write(line + "\n")
                        output_file.flush()

                        if data_str == "[DONE]":
                            print("  [DONE]")
                            break

                        try:
                            data = json.loads(data_str)
                            t = data.get("type", "")

                            if t == "stage":
                                print(f"  ⏳ {data.get('message', '')}")
                            elif t == "claims_extracted":
                                print(f"  📋 Extracted {data.get('count')} atomic claims (type: {data.get('claim_type')})")
                            elif t == "tier_searching":
                                print(f"  🔍 Tier {data.get('tier')} ({data.get('tier_name')}) searching...")
                            elif t == "tier_complete":
                                print(f"  ✅ Tier {data.get('tier')}: found {data.get('count')} results")
                            elif t == "evidence_scraped":
                                print(f"  📄 Scraped {data.get('chars')} chars from {data.get('url', '')[:60]}...")
                            elif t == "stance_result":
                                emoji = {"SUPPORTS": "👍", "REFUTES": "👎", "NOT_ENOUGH_INFO": "❓"}.get(data.get("stance"), "❓")
                                print(f"  {emoji} {data.get('stance')} (confidence: {data.get('confidence', 0):.2f}) - Tier {data.get('tier')}")
                            elif t == "verdict":
                                verdict_emoji = {"FAKE": "🔴", "UNVERIFIED": "🟡", "TRUE": "🟢"}.get(data.get("verdict"), "⚪")
                                print(f"\n  {'='*40}")
                                print(f"  {verdict_emoji} VERDICT: {data.get('verdict')}")
                                print(f"  Score: {data.get('veracity_score', 0):.4f}")
                                print(f"  Confidence: {data.get('confidence', 0):.4f}")
                                summary = data.get("sources_summary", {})
                                print(f"  Sources: 👍{summary.get('supports', 0)} | 👎{summary.get('refutes', 0)} | ❓{summary.get('neutral', 0)}")
                                print(f"  Explanation: {data.get('explanation', '')[:200]}...")
                                print(f"  {'='*40}")

                        except json.JSONDecodeError:
                            continue

    except Exception as e:
        print(f"  ❌ Failed: {e}")
        output_file.write(f"ERROR: {e}\n")


async def main():
    with open("verify_output.txt", "w", encoding="utf-8") as f:
        for claim in CLAIMS_TO_TEST:
            await test_verify(claim, f)

    print(f"\nFull log written to backend/verify_output.txt")


if __name__ == "__main__":
    asyncio.run(main())
