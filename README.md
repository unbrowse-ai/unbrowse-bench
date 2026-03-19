# Unbrowse WebArena-Style Benchmark

Compares Unbrowse (API-based web data extraction) vs Playwright (browser automation) on WebArena-style information retrieval tasks.

## Background

[WebArena](https://github.com/web-arena-x/webarena) is a benchmark with 812 tasks across self-hosted websites. Since the Docker setup requires 100GB+ and the Docker daemon was unavailable, this benchmark uses the **same site categories** (Wikipedia, Reddit, GitLab, GitHub, shopping) with public endpoints.

## Running

```bash
# Ensure Unbrowse is running on port 6969
curl http://localhost:6969/health

# Run benchmark
python3 bench.py
```

## Results

See [results/summary.md](results/summary.md) for the full breakdown.

**Key findings:**
- Unbrowse is **1.4-3.7x faster** than Playwright on cached sites (Reddit, GitHub)
- Playwright has **100% success** as a brute-force baseline
- Unbrowse saved **306,877 tokens** vs raw LLM extraction across 15 tasks
- 47% of Unbrowse "failures" were disambiguation issues (multiple endpoints), not capability gaps

## Files

- `tasks.json` -- 15 benchmark task definitions
- `bench.py` -- benchmark runner (async, runs both methods per task)
- `results/raw_results.json` -- full per-task results with timing
- `results/summary.md` -- human-readable summary
- `results/summary.json` -- machine-readable summary stats
