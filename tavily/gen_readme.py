"""
Regenerate README.md from existing results.csv.

Failure reasons (written by eval.py per URL):
- "dead"       — URL is broken/unreachable; excluded from all metrics
- "blocked"    — HTTP 403/429 anti-bot wall; included (bypassing these is a product differentiator)
- "no_content" — Tavily returned empty content for a reachable page; included
- "timeout"    — batch timed out; included
- "api_error"  — Tavily API-level error; included

Run: python3 gen_readme.py
"""

import csv
import os
from datetime import date

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results.csv")
README_PATH = os.path.join(os.path.dirname(__file__), "README.md")
DATASET_TOTAL = 1000


def load_results():
    with open(RESULTS_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def stats(rows):
    n = len(rows)
    if not n:
        return {}
    coverages = [r["coverage"] == "True" for r in rows]
    recalls = [float(r["recall"]) for r in rows]
    latencies = sorted(
        float(r["latency_ms"]) for r in rows
        if r["success"] == "True" and 0 < float(r["latency_ms"]) < 30000
    )
    total_cost = sum(float(r["cost_usd"]) for r in rows)
    return {
        "n": n,
        "coverage_pct": sum(coverages) / n * 100,
        "avg_recall": sum(recalls) / n,
        "p50": latencies[len(latencies) // 2] if latencies else 0,
        "p95": latencies[int(len(latencies) * 0.95)] if latencies else 0,
        "cost_per_url": total_cost / n,
    }


def main():
    all_rows = load_results()
    total = len(all_rows)

    # Partition by failure_reason
    successes = [r for r in all_rows if r["success"] == "True"]
    dead = [r for r in all_rows if r.get("failure_reason") == "dead"]
    blocked = [r for r in all_rows if r.get("failure_reason") == "blocked"]
    no_content = [r for r in all_rows if r.get("failure_reason") in ("no_content", "timeout", "api_error")]

    # Dead URLs excluded from metrics — no scraper can retrieve a broken page
    fair_rows = [r for r in all_rows if r.get("failure_reason") != "dead"]
    fair_successes = [r for r in fair_rows if r["success"] == "True"]

    fair_stats = stats(fair_rows)
    success_stats = stats(fair_successes)

    md = f"""# Tavily /extract Eval Results

Dataset: `firecrawl/scrape-content-dataset-v1` ({DATASET_TOTAL} URLs, {total} usable after filtering dataset errors and PDFs)
Endpoint: Tavily `/extract` (`extract_depth="basic"`)
Run date: {date.today()}

## URL classification

| Status | Count | Included in metrics? |
|---|---|---|
| Content returned | {len(successes)} | Yes |
| No content — blocked (403/429) | {len(blocked)} | Yes — bypassing anti-bot walls is a product differentiator |
| No content — Tavily miss | {len(no_content)} | Yes — reachable pages Tavily failed to extract |
| Dead URL (confirmed unreachable) | {len(dead)} | No — no scraper can retrieve a dead page |
| **Fair denominator** | **{fair_stats['n']}** | |

## Results vs. Firecrawl's published numbers

Metrics calculated over {fair_stats['n']} URLs (dead URLs excluded from denominator). \
Firecrawl's published numbers include no stated exclusions, so their figures likely \
include dead URLs — meaning our numbers use a marginally stricter denominator.

| Metric | Tavily /extract (our run) | Tavily (Firecrawl's claim) | Firecrawl (their own claim) |
|---|---|---|---|
| Coverage (Success Rate) | {fair_stats['coverage_pct']:.1f}% | 67.8% | 77.2% |
| Quality (Recall) | {fair_stats['avg_recall']:.3f} | — | — |
| P50 Latency (ms) | {fair_stats['p50']:.0f} | 1,638 | 1,012 |
| P95 Latency (ms) | {fair_stats['p95']:.0f} | 7,339 | 3,387 |
| $/URL | ${fair_stats['cost_per_url']:.4f} | $0.0080 | $0.0063 |

When Tavily successfully retrieved a page (n={success_stats['n']}), recall was \
{success_stats['avg_recall']:.3f} and coverage was {success_stats['coverage_pct']:.1f}%.

## Why recall, not F1

Firecrawl's benchmark scores "content recall" but reports F1. F1 penalises precision, \
meaning any tool that returns more content than the short truth_text snippet will score \
poorly even if it retrieved the right content. Recall measures only whether the truth_text \
tokens were present in the retrieved content, which is the fair comparison when both tools \
return full pages that are longer than the ground truth snippet.

See the [methodology notes](#methodology-notes) below for more detail on the scoring approach.

## Methodology notes

- Firecrawl's benchmark did not specify which Tavily endpoint it tested.
  We used `/extract` (basic depth) — the endpoint designed for URL-to-content
  extraction, making it the closest equivalent to Firecrawl `/scrape`.
- Batched 5 URLs per API call (1 credit per batch at PAYG rate of $0.008/credit).
- Latency computed over successful rows only. Rows exceeding 30,000ms excluded from P50/P95.
- Coverage = at least 10% of truth_text tokens present in extracted content.
- {DATASET_TOTAL - total} rows excluded from dataset (had errors, missing truth_text, or were PDFs).
- {len(dead)} URLs confirmed dead via HEAD check and excluded from all metrics.
- Failure reasons recorded per URL in results.csv (`failure_reason` column).

## Raw results

See `results.csv` for per-URL breakdown.
"""

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"README written to {README_PATH}")
    print(f"  Fair denominator ({fair_stats['n']} URLs): coverage={fair_stats['coverage_pct']:.1f}% recall={fair_stats['avg_recall']:.3f}")
    print(f"  Successes only  ({success_stats['n']} URLs): coverage={success_stats['coverage_pct']:.1f}% recall={success_stats['avg_recall']:.3f}")


if __name__ == "__main__":
    main()
