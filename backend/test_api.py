import json
import httpx
import asyncio
import sys

async def test_web_search():
    url = "http://localhost:8080/web-search"
    payload = {
        "query": "What is the latest status of the OpenAI Sora model?",
        "conversation_id": "test-conv-123",
        "num_results": 15,
        "use_rag": False
    }
    
    print(f"Connecting to {url}...")
    output_file = open("output.txt", "w", encoding="utf-8")
    
    try:
        # Increase timeout drastically to accommodate scraping 15-20 sites
        async with httpx.AsyncClient(timeout=600.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    err_msg = f"Error: {response.status_code}\n"
                    print(err_msg)
                    output_file.write(err_msg)
                    body = await response.aread()
                    output_file.write(body.decode())
                    return

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                        
                    if line.startswith("data: "):
                        data_str = line[6:]
                        
                        # Log raw data to file
                        output_file.write(line + "\n")
                        output_file.flush()
                        
                        if data_str == "[DONE]":
                            print("\n[DONE]")
                            break
                        
                        try:
                            data = json.loads(data_str)
                            
                            # Simple progress indicator for console
                            if "type" in data:
                                t = data["type"]
                                if t == "searching":
                                    print(f"STATUS: Searching for '{data.get('query')}'...")
                                elif t == "found":
                                    print(f"STATUS: Found {data.get('total')} URLs.")
                                elif t == "scraping":
                                    print(f"STATUS: Scraping {data.get('url')} ({data.get('index')}/{data.get('total')})...")
                                elif t == "scraped":
                                    print(f"STATUS: Scraped {data.get('chars')} chars from {data.get('url')}")
                                elif t == "summarizing":
                                    print("STATUS: Summarizing and generating response...")
                            
                            # Stream actual content to console
                            if "content" in data:
                                print(data["content"], end="", flush=True)
                                
                        except json.JSONDecodeError:
                            continue
                            
    except Exception as e:
        err_msg = f"\nFailed to connect: {e}\n"
        print(err_msg)
        output_file.write(err_msg)
    finally:
        output_file.close()
        print(f"\nFull log written to backend/output.txt")

if __name__ == "__main__":
    asyncio.run(test_web_search())
