#!/usr/bin/env python3
"""WebArena benchmark: Unbrowse vs Playwright baseline."""

import json
import time
import requests
import subprocess
import sys
import os
from datetime import datetime

UNBROWSE_URL = "http://localhost:6969"
SHOPPING_URL = "http://localhost:7770"
REDDIT_URL = "http://localhost:9999"
WIKIPEDIA_URL = "http://localhost:8888"

SITE_URL_MAP = {
    "shopping": SHOPPING_URL,
    "reddit": REDDIT_URL,
    "wikipedia": WIKIPEDIA_URL,
}

# Placeholder replacements used in WebArena tasks
PLACEHOLDER_MAP = {
    "__SHOPPING__": SHOPPING_URL,
    "__REDDIT__": REDDIT_URL,
    "__WIKIPEDIA__": WIKIPEDIA_URL,
}


def resolve_start_url(task):
    url = task.get("start_url", "")
    for placeholder, base in PLACEHOLDER_MAP.items():
        url = url.replace(placeholder, base)
    return url


def run_unbrowse(task):
    """Run a task through Unbrowse intent resolution."""
    site = task["sites"][0]
    base_url = SITE_URL_MAP.get(site)
    if not base_url:
        return {"success": False, "error": f"Unknown site: {site}", "latency_ms": 0}

    start_url = resolve_start_url(task)
    if not start_url or start_url == base_url:
        start_url = base_url + "/"

    payload = {
        "intent": task["intent"],
        "context": {"url": start_url},
    }

    try:
        start = time.time()
        r = requests.post(
            f"{UNBROWSE_URL}/v1/intent/resolve",
            json=payload,
            timeout=60,
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
    """Run a task using simple Playwright page content extraction."""
    site = task["sites"][0]
    base_url = SITE_URL_MAP.get(site)
    if not base_url:
        return {"success": False, "error": f"Unknown site: {site}", "latency_ms": 0}

    start_url = resolve_start_url(task)
    if not start_url or start_url == base_url:
        start_url = base_url + "/"

    # Use a subprocess to run playwright
    script = f"""
import asyncio
from playwright.async_api import async_playwright
import time, json

async def main():
    start = time.time()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto("{start_url}", timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass
        content = await page.content()
        title = await page.title()
        text = await page.inner_text("body")
        await browser.close()
    elapsed_ms = int((time.time() - start) * 1000)
    print(json.dumps({{"success": True, "latency_ms": elapsed_ms, "title": title, "text_len": len(text)}}))

asyncio.run(main())
"""
    try:
        start = time.time()
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
        )
        elapsed_ms = int((time.time() - start) * 1000)
        if result.returncode == 0:
            data = json.loads(result.stdout.strip())
            data["latency_ms"] = elapsed_ms  # use wall time
            return data
        else:
            return {
                "success": False,
                "latency_ms": elapsed_ms,
                "error": result.stderr[:300],
            }
    except Exception as e:
        return {"success": False, "latency_ms": 0, "error": str(e)}


def evaluate_answer(unbrowse_response, task):
    """Check if unbrowse response matches expected answer."""
    eval_info = task.get("eval", {})
    ref = eval_info.get("reference_answers", {})
    
    if not unbrowse_response.get("success"):
        return False
    
    response_data = unbrowse_response.get("response", {})
    answer_text = json.dumps(response_data).lower()
    
    # Check exact match
    if "exact_match" in ref:
        expected = ref["exact_match"].lower()
        return expected in answer_text
    
    # Check must_include
    if "must_include" in ref:
        return all(item.lower() in answer_text for item in ref["must_include"])
    
    return None  # Can't evaluate


def main():
    tasks_file = os.path.join(os.path.dirname(__file__), "selected_tasks.json")
    with open(tasks_file) as f:
        tasks = json.load(f)

    # Check which sites are available
    available_sites = set()
    for site, url in SITE_URL_MAP.items():
        try:
            r = requests.get(url, timeout=5)
            if r.status_code < 500:
                available_sites.add(site)
                print(f"[OK] {site} at {url} (HTTP {r.status_code})")
        except:
            print(f"[SKIP] {site} at {url} - not available")

    # Filter tasks to available sites
    tasks = [t for t in tasks if t["sites"][0] in available_sites]
    print(f"\nRunning {len(tasks)} tasks on sites: {available_sites}\n")

    if not tasks:
        print("No sites available! Start Docker containers first.")
        sys.exit(1)

    results = []
    for i, task in enumerate(tasks):
        task_id = task["task_id"]
        intent = task["intent"]
        site = task["sites"][0]
        print(f"[{i+1}/{len(tasks)}] Task {task_id} ({site}): {intent[:60]}...")

        # Run unbrowse
        ub_result = run_unbrowse(task)
        print(f"  Unbrowse: {'OK' if ub_result['success'] else 'FAIL'} ({ub_result['latency_ms']}ms)")

        # Run playwright
        pw_result = run_playwright(task)
        print(f"  Playwright: {'OK' if pw_result['success'] else 'FAIL'} ({pw_result['latency_ms']}ms)")

        # Evaluate
        match = evaluate_answer(ub_result, task)

        speedup = 0
        if pw_result.get("latency_ms", 0) > 0 and ub_result.get("latency_ms", 0) > 0:
            speedup = round(pw_result["latency_ms"] / ub_result["latency_ms"], 2)

        result = {
            "task_id": task_id,
            "intent": intent,
            "site": site,
            "unbrowse": {
                "success": ub_result.get("success", False),
                "latency_ms": ub_result.get("latency_ms", 0),
                "source": ub_result.get("source", "unknown"),
                "answer_match": match,
            },
            "playwright": {
                "success": pw_result.get("success", False),
                "latency_ms": pw_result.get("latency_ms", 0),
            },
            "speedup": speedup,
        }
        results.append(result)

        # Save intermediate results
        output_file = os.path.join(os.path.dirname(__file__), "results", "webarena_real_results.json")
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    ub_successes = sum(1 for r in results if r["unbrowse"]["success"])
    pw_successes = sum(1 for r in results if r["playwright"]["success"])
    avg_ub_latency = sum(r["unbrowse"]["latency_ms"] for r in results) / max(len(results), 1)
    avg_pw_latency = sum(r["playwright"]["latency_ms"] for r in results) / max(len(results), 1)
    avg_speedup = sum(r["speedup"] for r in results) / max(len(results), 1)
    
    matches = [r for r in results if r["unbrowse"]["answer_match"] is True]
    
    print(f"Tasks: {len(results)}")
    print(f"Unbrowse success: {ub_successes}/{len(results)}")
    print(f"Playwright success: {pw_successes}/{len(results)}")
    print(f"Unbrowse answer match: {len(matches)}/{len(results)}")
    print(f"Avg Unbrowse latency: {avg_ub_latency:.0f}ms")
    print(f"Avg Playwright latency: {avg_pw_latency:.0f}ms")
    print(f"Avg speedup: {avg_speedup:.2f}x")

    # Save summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_tasks": len(results),
        "unbrowse_success_rate": ub_successes / max(len(results), 1),
        "playwright_success_rate": pw_successes / max(len(results), 1),
        "unbrowse_answer_match_rate": len(matches) / max(len(results), 1),
        "avg_unbrowse_latency_ms": round(avg_ub_latency),
        "avg_playwright_latency_ms": round(avg_pw_latency),
        "avg_speedup": round(avg_speedup, 2),
        "sites_tested": list(available_sites),
    }
    summary_file = os.path.join(os.path.dirname(__file__), "results", "summary.json")
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\nResults saved to {output_file}")


if __name__ == "__main__":
    main()
