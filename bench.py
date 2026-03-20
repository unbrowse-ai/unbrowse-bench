#!/usr/bin/env python3
"""
WebArena-style benchmark: Unbrowse vs Playwright browser automation.

Runs the same information retrieval tasks through both approaches and
compares latency, success rate, and resource usage.
"""

import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

BENCH_DIR = Path(__file__).parent
RESULTS_DIR = BENCH_DIR / "results"
TASKS_FILE = BENCH_DIR / "tasks.json"
UNBROWSE_URL = "http://localhost:6969/v1/intent/resolve"


# ── Unbrowse runner ──────────────────────────────────────────────────────────

async def run_unbrowse(task: dict, client: httpx.AsyncClient) -> dict:
    """Call Unbrowse resolve endpoint and return result + timing."""
    payload = {
        "intent": task["intent"],
        "params": {},
        "context": {"url": task["url"]},
    }
    t0 = time.monotonic()
    try:
        resp = await client.post(UNBROWSE_URL, json=payload, timeout=60)
        elapsed_ms = (time.monotonic() - t0) * 1000
        data = resp.json()
        result_text = json.dumps(data.get("result", ""))
        timing = data.get("timing", {})
        pattern = task.get("expected_pattern", "")
        matched = bool(re.search(pattern, result_text, re.IGNORECASE)) if pattern else None
        return {
            "method": "unbrowse",
            "task_id": task["id"],
            "success": matched,
            "latency_ms": round(elapsed_ms, 1),
            "server_total_ms": timing.get("total_ms"),
            "execute_ms": timing.get("execute_ms"),
            "cache_hit": timing.get("cache_hit"),
            "tokens_saved": timing.get("tokens_saved"),
            "result_snippet": result_text[:300],
            "error": None,
        }
    except Exception as e:
        elapsed_ms = (time.monotonic() - t0) * 1000
        return {
            "method": "unbrowse",
            "task_id": task["id"],
            "success": False,
            "latency_ms": round(elapsed_ms, 1),
            "server_total_ms": None,
            "execute_ms": None,
            "cache_hit": None,
            "tokens_saved": None,
            "result_snippet": None,
            "error": str(e),
        }


# ── Playwright runner ────────────────────────────────────────────────────────

async def run_playwright(task: dict) -> dict:
    """Use Playwright to load the page, extract text, and check for answer."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {
            "method": "playwright",
            "task_id": task["id"],
            "success": None,
            "latency_ms": None,
            "error": "playwright not installed",
            "result_snippet": None,
        }

    t0 = time.monotonic()
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            await page.goto(task["url"], wait_until="domcontentloaded", timeout=30000)
            # Wait a bit for JS rendering
            await page.wait_for_timeout(2000)
            text = await page.inner_text("body")
            elapsed_ms = (time.monotonic() - t0) * 1000
            await browser.close()

        pattern = task.get("expected_pattern", "")
        matched = bool(re.search(pattern, text, re.IGNORECASE)) if pattern else None
        return {
            "method": "playwright",
            "task_id": task["id"],
            "success": matched,
            "latency_ms": round(elapsed_ms, 1),
            "result_snippet": text[:300],
            "error": None,
        }
    except Exception as e:
        elapsed_ms = (time.monotonic() - t0) * 1000
        return {
            "method": "playwright",
            "task_id": task["id"],
            "success": False,
            "latency_ms": round(elapsed_ms, 1),
            "result_snippet": None,
            "error": str(e),
        }


# ── Main ─────────────────────────────────────────────────────────────────────

async def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    tasks = json.loads(TASKS_FILE.read_text())

    print(f"Running {len(tasks)} tasks...")
    all_results = []

    async with httpx.AsyncClient() as client:
        for i, task in enumerate(tasks):
            print(f"\n[{i+1}/{len(tasks)}] {task['id']}: {task['intent']}")

            # Run Unbrowse
            print("  → Unbrowse...", end=" ", flush=True)
            ub_result = await run_unbrowse(task, client)
            status = "OK" if ub_result["success"] else "FAIL"
            print(f"{status} ({ub_result['latency_ms']:.0f}ms)")

            # Run Playwright
            print("  → Playwright...", end=" ", flush=True)
            pw_result = await run_playwright(task)
            if pw_result.get("error"):
                print(f"ERR: {pw_result['error']}")
            else:
                status = "OK" if pw_result["success"] else "FAIL"
                print(f"{status} ({pw_result['latency_ms']:.0f}ms)")

            all_results.append({"task": task, "unbrowse": ub_result, "playwright": pw_result})

            # Save intermediate results
            (RESULTS_DIR / "raw_results.json").write_text(json.dumps(all_results, indent=2))

    # Generate summary
    generate_summary(all_results)


def generate_summary(results: list):
    """Generate markdown summary table and stats."""
    ub_successes = sum(1 for r in results if r["unbrowse"]["success"])
    pw_successes = sum(1 for r in results if r["playwright"]["success"])
    ub_latencies = [r["unbrowse"]["latency_ms"] for r in results if r["unbrowse"]["latency_ms"]]
    pw_latencies = [r["playwright"]["latency_ms"] for r in results if r["playwright"]["latency_ms"]]

    total = len(results)
    ub_avg = sum(ub_latencies) / len(ub_latencies) if ub_latencies else 0
    pw_avg = sum(pw_latencies) / len(pw_latencies) if pw_latencies else 0

    lines = [
        "# Unbrowse vs Playwright: WebArena-Style Benchmark Results",
        "",
        f"**Date**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Tasks**: {total}",
        "",
        "## Summary",
        "",
        "| Metric | Unbrowse | Playwright |",
        "|--------|----------|------------|",
        f"| Success Rate | {ub_successes}/{total} ({100*ub_successes/total:.0f}%) | {pw_successes}/{total} ({100*pw_successes/total:.0f}%) |",
        f"| Avg Latency | {ub_avg:.0f}ms | {pw_avg:.0f}ms |",
        f"| Median Latency | {sorted(ub_latencies)[len(ub_latencies)//2]:.0f}ms | {sorted(pw_latencies)[len(pw_latencies)//2]:.0f}ms |" if ub_latencies and pw_latencies else "",
        f"| Speedup | {pw_avg/ub_avg:.1f}x faster | baseline |" if ub_avg > 0 and pw_avg > 0 else "",
        "",
        "## Per-Task Results",
        "",
        "| Task | Category | Unbrowse | UB ms | Playwright | PW ms | Speedup |",
        "|------|----------|----------|-------|------------|-------|---------|",
    ]

    for r in results:
        t = r["task"]
        ub = r["unbrowse"]
        pw = r["playwright"]
        ub_ok = "PASS" if ub["success"] else "FAIL"
        pw_ok = "PASS" if pw["success"] else ("ERR" if pw.get("error") else "FAIL")
        ub_ms = f"{ub['latency_ms']:.0f}" if ub["latency_ms"] else "N/A"
        pw_ms = f"{pw['latency_ms']:.0f}" if pw.get("latency_ms") else "N/A"
        speedup = ""
        if ub["latency_ms"] and pw.get("latency_ms") and ub["latency_ms"] > 0:
            speedup = f"{pw['latency_ms']/ub['latency_ms']:.1f}x"
        lines.append(f"| {t['id']} | {t['category']} | {ub_ok} | {ub_ms} | {pw_ok} | {pw_ms} | {speedup} |")

    # Cache hit stats
    cache_hits = sum(1 for r in results if r["unbrowse"].get("cache_hit"))
    tokens_saved = sum(r["unbrowse"].get("tokens_saved", 0) or 0 for r in results)
    lines.extend([
        "",
        "## Unbrowse Details",
        "",
        f"- Cache hits: {cache_hits}/{total}",
        f"- Total tokens saved (vs raw LLM): {tokens_saved:,}",
        "",
        "## Notes",
        "",
        "- Docker was unavailable, so public versions of WebArena target sites were used",
        "- Tasks mirror WebArena's information retrieval category",
        "- Playwright baseline measures full browser load + text extraction",
        "- Unbrowse uses cached API skills where available, falling back to live extraction",
    ])

    summary = "\n".join(lines) + "\n"
    (RESULTS_DIR / "summary.md").write_text(summary)
    (RESULTS_DIR / "summary.json").write_text(json.dumps({
        "total_tasks": total,
        "unbrowse_successes": ub_successes,
        "playwright_successes": pw_successes,
        "unbrowse_avg_latency_ms": round(ub_avg, 1),
        "playwright_avg_latency_ms": round(pw_avg, 1),
        "speedup": round(pw_avg / ub_avg, 2) if ub_avg > 0 and pw_avg > 0 else None,
    }, indent=2))

    print("\n" + summary)
    print(f"Results saved to {RESULTS_DIR}/")


if __name__ == "__main__":
    asyncio.run(main())
