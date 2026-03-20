#!/usr/bin/env python3
"""
Preliminary WebArena benchmark: tests Unbrowse against WebArena-style tasks
using the task definitions and publicly accessible equivalents.

When the actual WebArena Docker containers are available, run run_benchmark.py instead.
"""

import json
import time
import requests
import subprocess
import sys
import os
from datetime import datetime

UNBROWSE_URL = "http://localhost:6969"

# Map WebArena task patterns to real public equivalents for testing
PUBLIC_TASK_EQUIVALENTS = [
    # Shopping/E-commerce tasks (Amazon-like)
    {
        "task_id": "wa_equiv_1",
        "intent": "Find reviews that mention battery life for wireless headphones",
        "url": "https://www.amazon.com/dp/B09WX4GJ5T",
        "site": "shopping",
        "category": "review_search",
    },
    {
        "task_id": "wa_equiv_2", 
        "intent": "What is the price of the most popular wireless mouse?",
        "url": "https://www.amazon.com/s?k=wireless+mouse&s=review-rank",
        "site": "shopping",
        "category": "product_info",
    },
    {
        "task_id": "wa_equiv_3",
        "intent": "Search for 'usb c hub' and tell me the top result",
        "url": "https://www.amazon.com",
        "site": "shopping",
        "category": "search",
    },
    {
        "task_id": "wa_equiv_4",
        "intent": "How many reviews does the top-rated laptop stand have?",
        "url": "https://www.amazon.com/s?k=laptop+stand&s=review-rank",
        "site": "shopping",
        "category": "product_info",
    },
    {
        "task_id": "wa_equiv_5",
        "intent": "What is the average rating for mechanical keyboards under $50?",
        "url": "https://www.amazon.com/s?k=mechanical+keyboard&rh=p_36%3A-5000",
        "site": "shopping",
        "category": "aggregation",
    },
    # Reddit/Forum tasks
    {
        "task_id": "wa_equiv_6",
        "intent": "What is the most upvoted post in r/programming this week?",
        "url": "https://old.reddit.com/r/programming/top/?sort=top&t=week",
        "site": "reddit",
        "category": "content_retrieval",
    },
    {
        "task_id": "wa_equiv_7",
        "intent": "How many comments does the top post in r/technology have?",
        "url": "https://old.reddit.com/r/technology/top/?sort=top&t=day",
        "site": "reddit",
        "category": "count",
    },
    {
        "task_id": "wa_equiv_8",
        "intent": "Find posts mentioning 'artificial intelligence' in r/technology",
        "url": "https://old.reddit.com/r/technology/search?q=artificial+intelligence&restrict_sr=on",
        "site": "reddit",
        "category": "search",
    },
    {
        "task_id": "wa_equiv_9",
        "intent": "Who is the author of the newest post in r/python?",
        "url": "https://old.reddit.com/r/python/new/",
        "site": "reddit",
        "category": "content_retrieval",
    },
    {
        "task_id": "wa_equiv_10",
        "intent": "What subreddit rules does r/webdev have?",
        "url": "https://old.reddit.com/r/webdev/about/rules/",
        "site": "reddit",
        "category": "info_retrieval",
    },
    # Wikipedia tasks
    {
        "task_id": "wa_equiv_11",
        "intent": "What is the population of Tokyo according to Wikipedia?",
        "url": "https://en.wikipedia.org/wiki/Tokyo",
        "site": "wikipedia",
        "category": "fact_retrieval",
    },
    {
        "task_id": "wa_equiv_12",
        "intent": "When was Python programming language first released?",
        "url": "https://en.wikipedia.org/wiki/Python_(programming_language)",
        "site": "wikipedia",
        "category": "fact_retrieval",
    },
    {
        "task_id": "wa_equiv_13",
        "intent": "List the founding members of the European Union",
        "url": "https://en.wikipedia.org/wiki/European_Union",
        "site": "wikipedia",
        "category": "list_extraction",
    },
    {
        "task_id": "wa_equiv_14",
        "intent": "What is the height of Mount Everest?",
        "url": "https://en.wikipedia.org/wiki/Mount_Everest",
        "site": "wikipedia",
        "category": "fact_retrieval",
    },
    {
        "task_id": "wa_equiv_15",
        "intent": "Who wrote the novel '1984'?",
        "url": "https://en.wikipedia.org/wiki/Nineteen_Eighty-Four",
        "site": "wikipedia",
        "category": "fact_retrieval",
    },
    # More shopping
    {
        "task_id": "wa_equiv_16",
        "intent": "Show me the cheapest HDMI cable available",
        "url": "https://www.amazon.com/s?k=hdmi+cable&s=price-asc-rank",
        "site": "shopping",
        "category": "search",
    },
    {
        "task_id": "wa_equiv_17",
        "intent": "What brands of webcams are available?",
        "url": "https://www.amazon.com/s?k=webcam",
        "site": "shopping",
        "category": "list_extraction",
    },
    # More reddit
    {
        "task_id": "wa_equiv_18",
        "intent": "What is the sidebar description of r/javascript?",
        "url": "https://old.reddit.com/r/javascript/",
        "site": "reddit",
        "category": "info_retrieval",
    },
    {
        "task_id": "wa_equiv_19",
        "intent": "How many subscribers does r/MachineLearning have?",
        "url": "https://old.reddit.com/r/MachineLearning/",
        "site": "reddit",
        "category": "count",
    },
    {
        "task_id": "wa_equiv_20",
        "intent": "Find the newest post about 'rust programming language' on reddit",
        "url": "https://old.reddit.com/search?q=rust+programming+language&sort=new",
        "site": "reddit",
        "category": "search",
    },
    # More Wikipedia
    {
        "task_id": "wa_equiv_21",
        "intent": "What are the official languages of Switzerland?",
        "url": "https://en.wikipedia.org/wiki/Switzerland",
        "site": "wikipedia",
        "category": "fact_retrieval",
    },
    {
        "task_id": "wa_equiv_22",
        "intent": "When was the first iPhone released?",
        "url": "https://en.wikipedia.org/wiki/IPhone",
        "site": "wikipedia",
        "category": "fact_retrieval",
    },
    {
        "task_id": "wa_equiv_23",
        "intent": "What is the chemical formula of water?",
        "url": "https://en.wikipedia.org/wiki/Water",
        "site": "wikipedia",
        "category": "fact_retrieval",
    },
    {
        "task_id": "wa_equiv_24",
        "intent": "List the planets in our solar system",
        "url": "https://en.wikipedia.org/wiki/Solar_System",
        "site": "wikipedia",
        "category": "list_extraction",
    },
    {
        "task_id": "wa_equiv_25",
        "intent": "What is the GDP of the United States?",
        "url": "https://en.wikipedia.org/wiki/United_States",
        "site": "wikipedia",
        "category": "fact_retrieval",
    },
    # Additional mixed tasks
    {
        "task_id": "wa_equiv_26",
        "intent": "Compare the prices of the top 3 USB-C chargers",
        "url": "https://www.amazon.com/s?k=usb-c+charger",
        "site": "shopping",
        "category": "comparison",
    },
    {
        "task_id": "wa_equiv_27",
        "intent": "What is the most discussed topic in r/science today?",
        "url": "https://old.reddit.com/r/science/hot/",
        "site": "reddit",
        "category": "content_retrieval",
    },
    {
        "task_id": "wa_equiv_28",
        "intent": "What year did World War II end?",
        "url": "https://en.wikipedia.org/wiki/World_War_II",
        "site": "wikipedia",
        "category": "fact_retrieval",
    },
    {
        "task_id": "wa_equiv_29",
        "intent": "Find wireless earbuds with noise cancellation under $100",
        "url": "https://www.amazon.com/s?k=wireless+earbuds+noise+cancellation&rh=p_36%3A-10000",
        "site": "shopping",
        "category": "search",
    },
    {
        "task_id": "wa_equiv_30",
        "intent": "What are the pinned posts in r/learnprogramming?",
        "url": "https://old.reddit.com/r/learnprogramming/",
        "site": "reddit",
        "category": "content_retrieval",
    },
]


def run_unbrowse(task):
    """Run a task through Unbrowse intent resolution."""
    payload = {
        "intent": task["intent"],
        "context": {"url": task["url"]},
    }
    try:
        start = time.time()
        r = requests.post(
            f"{UNBROWSE_URL}/v1/intent/resolve",
            json=payload,
            timeout=120,
        )
        elapsed_ms = int((time.time() - start) * 1000)
        if r.status_code == 200:
            data = r.json()
            return {
                "success": True,
                "latency_ms": elapsed_ms,
                "response": data,
                "source": data.get("source", "unknown"),
            }
        else:
            return {
                "success": False,
                "latency_ms": elapsed_ms,
                "error": f"HTTP {r.status_code}: {r.text[:200]}",
            }
    except Exception as e:
        return {"success": False, "latency_ms": 0, "error": str(e)}


def run_playwright(task):
    """Run a task using Playwright page content extraction."""
    url = task["url"]
    script = f'''
import asyncio
from playwright.async_api import async_playwright
import time, json

async def main():
    start = time.time()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await ctx.new_page()
        try:
            await page.goto("{url}", timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass
        content = await page.content()
        title = await page.title()
        try:
            text = await page.inner_text("body")
        except:
            text = ""
        await browser.close()
    elapsed_ms = int((time.time() - start) * 1000)
    print(json.dumps({{"success": True, "latency_ms": elapsed_ms, "title": title, "text_len": len(text), "html_len": len(content)}}))

asyncio.run(main())
'''
    try:
        start = time.time()
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=60,
        )
        elapsed_ms = int((time.time() - start) * 1000)
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            data["latency_ms"] = elapsed_ms
            return data
        else:
            return {"success": False, "latency_ms": elapsed_ms, "error": result.stderr[:300]}
    except Exception as e:
        return {"success": False, "latency_ms": 0, "error": str(e)}


def main():
    tasks = PUBLIC_TASK_EQUIVALENTS
    
    # Verify Unbrowse is running
    try:
        r = requests.get(f"{UNBROWSE_URL}/health", timeout=5)
        print(f"Unbrowse: {r.json()}")
    except:
        print("ERROR: Unbrowse not available at localhost:6969")
        sys.exit(1)

    results = []
    output_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'='*70}")
    print(f"WebArena-equivalent Benchmark: {len(tasks)} tasks")
    print(f"{'='*70}\n")

    for i, task in enumerate(tasks):
        tid = task["task_id"]
        intent = task["intent"]
        site = task["site"]
        cat = task["category"]
        
        print(f"[{i+1}/{len(tasks)}] {tid} ({site}/{cat}): {intent[:55]}...")

        # Run unbrowse
        ub = run_unbrowse(task)
        ub_status = "OK" if ub["success"] else "FAIL"
        print(f"  Unbrowse: {ub_status} ({ub['latency_ms']}ms) src={ub.get('source','?')}")

        # Run playwright  
        pw = run_playwright(task)
        pw_status = "OK" if pw["success"] else "FAIL"
        print(f"  Playwright: {pw_status} ({pw['latency_ms']}ms)")

        speedup = 0
        if pw.get("latency_ms", 0) > 0 and ub.get("latency_ms", 0) > 0:
            speedup = round(pw["latency_ms"] / ub["latency_ms"], 2)

        result = {
            "task_id": tid,
            "intent": intent,
            "site": site,
            "category": cat,
            "url": task["url"],
            "unbrowse": {
                "success": ub.get("success", False),
                "latency_ms": ub.get("latency_ms", 0),
                "source": ub.get("source", "unknown"),
                "error": ub.get("error"),
            },
            "playwright": {
                "success": pw.get("success", False),
                "latency_ms": pw.get("latency_ms", 0),
                "error": pw.get("error"),
            },
            "speedup": speedup,
        }
        results.append(result)

        # Save intermediate
        with open(os.path.join(output_dir, "webarena_equiv_results.json"), "w") as f:
            json.dump(results, f, indent=2)

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")

    ub_ok = sum(1 for r in results if r["unbrowse"]["success"])
    pw_ok = sum(1 for r in results if r["playwright"]["success"])
    both_ok = [r for r in results if r["unbrowse"]["success"] and r["playwright"]["success"]]
    
    avg_ub = sum(r["unbrowse"]["latency_ms"] for r in results) / max(len(results), 1)
    avg_pw = sum(r["playwright"]["latency_ms"] for r in results) / max(len(results), 1)
    
    if both_ok:
        avg_speedup_both = sum(r["speedup"] for r in both_ok) / len(both_ok)
    else:
        avg_speedup_both = 0

    # By site
    for site in ["shopping", "reddit", "wikipedia"]:
        site_results = [r for r in results if r["site"] == site]
        if not site_results:
            continue
        s_ub = sum(1 for r in site_results if r["unbrowse"]["success"])
        s_pw = sum(1 for r in site_results if r["playwright"]["success"])
        s_ub_lat = sum(r["unbrowse"]["latency_ms"] for r in site_results) / len(site_results)
        s_pw_lat = sum(r["playwright"]["latency_ms"] for r in site_results) / len(site_results)
        print(f"\n  {site}:")
        print(f"    Unbrowse:   {s_ub}/{len(site_results)} success, avg {s_ub_lat:.0f}ms")
        print(f"    Playwright: {s_pw}/{len(site_results)} success, avg {s_pw_lat:.0f}ms")

    # Source distribution
    from collections import Counter
    sources = Counter(r["unbrowse"]["source"] for r in results if r["unbrowse"]["success"])
    
    print(f"\n  Overall:")
    print(f"    Tasks: {len(results)}")
    print(f"    Unbrowse success: {ub_ok}/{len(results)} ({100*ub_ok/len(results):.0f}%)")
    print(f"    Playwright success: {pw_ok}/{len(results)} ({100*pw_ok/len(results):.0f}%)")
    print(f"    Avg Unbrowse latency: {avg_ub:.0f}ms")
    print(f"    Avg Playwright latency: {avg_pw:.0f}ms")
    print(f"    Avg speedup (both OK): {avg_speedup_both:.2f}x")
    print(f"    Unbrowse sources: {dict(sources)}")

    summary = {
        "timestamp": datetime.now().isoformat(),
        "benchmark": "webarena_equivalent",
        "total_tasks": len(results),
        "unbrowse_success_rate": round(ub_ok / max(len(results), 1), 3),
        "playwright_success_rate": round(pw_ok / max(len(results), 1), 3),
        "avg_unbrowse_latency_ms": round(avg_ub),
        "avg_playwright_latency_ms": round(avg_pw),
        "avg_speedup": round(avg_speedup_both, 2),
        "source_distribution": dict(sources),
        "by_site": {},
    }
    for site in ["shopping", "reddit", "wikipedia"]:
        sr = [r for r in results if r["site"] == site]
        if sr:
            summary["by_site"][site] = {
                "tasks": len(sr),
                "unbrowse_success": sum(1 for r in sr if r["unbrowse"]["success"]),
                "playwright_success": sum(1 for r in sr if r["playwright"]["success"]),
                "avg_unbrowse_latency": round(sum(r["unbrowse"]["latency_ms"] for r in sr) / len(sr)),
                "avg_playwright_latency": round(sum(r["playwright"]["latency_ms"] for r in sr) / len(sr)),
            }

    with open(os.path.join(output_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nResults: {output_dir}/webarena_equiv_results.json")
    print(f"Summary: {output_dir}/summary.json")


if __name__ == "__main__":
    main()
