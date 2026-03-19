#!/usr/bin/env python3
"""WebArena-style benchmark with warm Unbrowse cache vs Playwright."""

import json
import time
import requests
import subprocess
import sys

UNBROWSE_URL = "http://localhost:6969/v1/intent/resolve"

def load_tasks():
    with open("/Users/lekt9/projects/unbrowse-webarena-bench/tasks.json") as f:
        tasks1 = json.load(f)
    with open("/Users/lekt9/projects/unbrowse-webarena-bench/results/webarena_equiv_results.json") as f:
        tasks2 = json.load(f)

    seen = set()
    tasks = []
    task_id = 0

    for t in tasks1:
        key = (t["url"], t["intent"])
        if key not in seen:
            seen.add(key)
            task_id += 1
            site = t.get("category", "unknown")
            tasks.append({"task_id": f"warm_{task_id}", "intent": t["intent"], "url": t["url"], "site": site})

    for t in tasks2:
        key = (t["url"], t["intent"])
        if key not in seen:
            seen.add(key)
            task_id += 1
            site = t.get("site", "unknown")
            tasks.append({"task_id": f"warm_{task_id}", "intent": t["intent"], "url": t["url"], "site": site})

    return tasks


def call_unbrowse(intent, url, timeout=60):
    payload = {"intent": intent, "context": {"url": url}}
    start = time.time()
    try:
        r = requests.post(UNBROWSE_URL, json=payload, timeout=timeout)
        elapsed = (time.time() - start) * 1000
        data = r.json()
        source = "unknown"
        timing_ms = elapsed
        if "result" in data:
            res = data["result"]
            if isinstance(res, dict):
                if "timing" in res and isinstance(res["timing"], dict):
                    timing_ms = res["timing"].get("total_ms", elapsed)
                source = res.get("source", "unknown")
        elif "source" in data:
            source = data["source"]
        if "timing" in data and isinstance(data["timing"], dict):
            timing_ms = data["timing"].get("total_ms", timing_ms)
        return {"success": True, "latency_ms": round(timing_ms, 1), "source": source, "wall_ms": round(elapsed, 1)}
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return {"success": False, "latency_ms": round(elapsed, 1), "source": "error", "wall_ms": round(elapsed, 1), "error": str(e)}


def call_playwright(url, timeout=30):
    script = '''
import json, time, sys
from playwright.sync_api import sync_playwright

url = sys.argv[1]
timeout_ms = int(sys.argv[2])
start = time.time()
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(2000)
        try:
            text = page.inner_text("body")
        except:
            text = ""
        elapsed = int((time.time() - start) * 1000)
        print(json.dumps({"success": True, "latency_ms": elapsed, "chars": len(text)}))
        browser.close()
except Exception as e:
    elapsed = int((time.time() - start) * 1000)
    print(json.dumps({"success": False, "latency_ms": elapsed, "error": str(e)}))
'''
    try:
        result = subprocess.run([sys.executable, "-c", script, url, str(timeout * 1000)], capture_output=True, text=True, timeout=timeout + 15)
        if result.stdout.strip():
            data = json.loads(result.stdout.strip().split('\n')[-1])
            return data
        return {"success": False, "latency_ms": 0, "error": result.stderr[:200]}
    except Exception as e:
        return {"success": False, "latency_ms": 0, "error": str(e)}


def main():
    tasks = load_tasks()
    print(f"Loaded {len(tasks)} unique tasks")

    results = []
    for i, task in enumerate(tasks):
        print(f"\n[{i+1}/{len(tasks)}] {task['task_id']}: {task['intent'][:60]}...")
        print(f"  URL: {task['url']}")

        # Warmup call (ignore result)
        print("  Unbrowse warmup...", end=" ", flush=True)
        warmup = call_unbrowse(task["intent"], task["url"])
        print(f"{warmup['wall_ms']:.0f}ms ({warmup.get('source', '?')})")

        # Real measurement call
        print("  Unbrowse measured...", end=" ", flush=True)
        unbrowse = call_unbrowse(task["intent"], task["url"])
        print(f"{unbrowse['wall_ms']:.0f}ms ({unbrowse.get('source', '?')})")

        # Playwright call
        print("  Playwright...", end=" ", flush=True)
        pw = call_playwright(task["url"])
        print(f"{pw.get('latency_ms', 0)}ms")

        pw_ms = pw.get("latency_ms", 0) or 1
        ub_ms = unbrowse.get("latency_ms", 1) or 1
        speedup = round(pw_ms / ub_ms, 2) if ub_ms > 0 else 0

        result = {
            "task_id": task["task_id"],
            "intent": task["intent"],
            "url": task["url"],
            "site": task["site"],
            "unbrowse_warm_ms": unbrowse["latency_ms"],
            "unbrowse_source": unbrowse.get("source", "unknown"),
            "playwright_ms": pw.get("latency_ms", 0),
            "speedup": speedup
        }
        results.append(result)

    # Save results
    out_path = "/Users/lekt9/projects/unbrowse-webarena-bench/results/warm_cache_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {out_path}")

    generate_summary(results)


def generate_summary(results):
    total = len(results)
    marketplace = [r for r in results if r["unbrowse_source"] == "marketplace"]
    route_cache = [r for r in results if r["unbrowse_source"] == "route-cache"]
    live = [r for r in results if r["unbrowse_source"] == "live-capture"]

    avg_ub = sum(r["unbrowse_warm_ms"] for r in results) / total if total else 0
    avg_pw = sum(r["playwright_ms"] for r in results) / total if total else 0
    avg_speedup = sum(r["speedup"] for r in results) / total if total else 0

    cached = marketplace + route_cache
    if cached:
        avg_cached_ub = sum(r["unbrowse_warm_ms"] for r in cached) / len(cached)
        avg_cached_pw = sum(r["playwright_ms"] for r in cached) / len(cached)
        avg_cached_speedup = sum(r["speedup"] for r in cached) / len(cached)
    else:
        avg_cached_ub = avg_cached_pw = avg_cached_speedup = 0

    median_speedup = sorted(r["speedup"] for r in results)[total // 2] if total else 0
    wins = sum(1 for r in results if r["speedup"] > 1)

    sites = {}
    for r in results:
        s = r["site"]
        if s not in sites:
            sites[s] = []
        sites[s].append(r)

    lines = []
    lines.append("# Warm Cache Benchmark Results")
    lines.append("")
    lines.append("**Date**: 2026-03-18")
    lines.append(f"**Total tasks**: {total}")
    lines.append(f"**Unbrowse wins**: {wins}/{total} ({100*wins/total:.0f}%)")
    lines.append("")
    lines.append("## Overall")
    lines.append("")
    lines.append("| Metric | Unbrowse (warm) | Playwright | Speedup |")
    lines.append("|--------|----------------|------------|---------|")
    lines.append(f"| Avg latency | {avg_ub:.0f}ms | {avg_pw:.0f}ms | {avg_speedup:.2f}x |")
    lines.append(f"| Median speedup | | | {median_speedup:.2f}x |")
    lines.append("")
    lines.append("## Cache Hit Rate")
    lines.append("")
    lines.append("| Source | Count | % |")
    lines.append("|--------|-------|---|")
    lines.append(f"| marketplace | {len(marketplace)} | {100*len(marketplace)/total:.0f}% |")
    lines.append(f"| route-cache | {len(route_cache)} | {100*len(route_cache)/total:.0f}% |")
    lines.append(f"| live-capture | {len(live)} | {100*len(live)/total:.0f}% |")
    lines.append("")

    if cached:
        lines.append("## Cached-only performance")
        lines.append("")
        lines.append("| Metric | Unbrowse | Playwright | Speedup |")
        lines.append("|--------|----------|------------|---------|")
        lines.append(f"| Avg latency | {avg_cached_ub:.0f}ms | {avg_cached_pw:.0f}ms | {avg_cached_speedup:.2f}x |")
        lines.append("")

    lines.append("## Per-site breakdown")
    lines.append("")
    lines.append("| Site | Tasks | Avg Unbrowse | Avg Playwright | Avg Speedup |")
    lines.append("|------|-------|-------------|----------------|-------------|")
    for site, rs in sorted(sites.items()):
        n = len(rs)
        au = sum(r["unbrowse_warm_ms"] for r in rs) / n
        ap = sum(r["playwright_ms"] for r in rs) / n
        asp = sum(r["speedup"] for r in rs) / n
        lines.append(f"| {site} | {n} | {au:.0f}ms | {ap:.0f}ms | {asp:.2f}x |")

    lines.append("")
    lines.append("## All tasks")
    lines.append("")
    lines.append("| Task | Site | Source | Unbrowse | Playwright | Speedup |")
    lines.append("|------|------|--------|----------|------------|---------|")
    for r in results:
        lines.append(f"| {r['task_id']} | {r['site']} | {r['unbrowse_source']} | {r['unbrowse_warm_ms']:.0f}ms | {r['playwright_ms']}ms | {r['speedup']:.2f}x |")

    summary = "\n".join(lines) + "\n"
    out = "/Users/lekt9/projects/unbrowse-webarena-bench/results/warm_cache_summary.md"
    with open(out, "w") as f:
        f.write(summary)
    print(f"Summary saved to {out}")


if __name__ == "__main__":
    main()
