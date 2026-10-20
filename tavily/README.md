# Tavily /extract Eval Results

Dataset: `firecrawl/scrape-content-dataset-v1` (1000 URLs, 834 usable after filtering dataset errors and PDFs)
Endpoint: Tavily `/extract` (`extract_depth="basic"`)
Run date: 2026-10-20

## URL classification

| Status | Count | Included in metrics? |
|---|---|---|
| Content returned | 603 | Yes |
| No content — blocked (403/429) | 90 | Yes — bypassing anti-bot walls is a product differentiator |
| No content — Tavily miss | 72 | Yes — reachable pages Tavily failed to extract |
| Dead URL (confirmed unreachable) | 69 | No — no scraper can retrieve a dead page |
| **Fair denominator** | **765** | |

## Results vs. Firecrawl's published numbers

Metrics calculated over 765 URLs (dead URLs excluded from denominator). Firecrawl's published numbers include no stated exclusions, so their figures likely include dead URLs — meaning our numbers use a marginally stricter denominator.

| Metric | Tavily /extract (our run) | Tavily (Firecrawl's claim) | Firecrawl (their own claim) |
|---|---|---|---|
| Coverage (Success Rate) | 73.5% | 67.8% | 77.2% |
| Quality (Recall) | 0.543 | — | — |
| P50 Latency (ms) | 538 | 1,638 | 1,012 |
| P95 Latency (ms) | 1626 | 7,339 | 3,387 |
| $/URL | $0.0012 | $0.0080 | $0.0063 |

When Tavily successfully retrieved a page (n=603), recall was 0.689 and coverage was 93.2%.

## Why recall, not F1

Firecrawl's benchmark scores "content recall" but reports F1. F1 penalises precision, meaning any tool that returns more content than the short truth_text snippet will score poorly even if it retrieved the right content. Recall measures only whether the truth_text tokens were present in the retrieved content, which is the fair comparison when both tools return full pages that are longer than the ground truth snippet.

See the [methodology notes](#methodology-notes) below for more detail on the scoring approach.

## Methodology notes

- Firecrawl's benchmark did not specify which Tavily endpoint it tested.
  We used `/extract` (basic depth) — the endpoint designed for URL-to-content
  extraction, making it the closest equivalent to Firecrawl `/scrape`.
- Batched 5 URLs per API call (1 credit per batch at PAYG rate of $0.008/credit).
- Latency computed over successful rows only. Rows exceeding 30,000ms excluded from P50/P95.
- Coverage = at least 10% of truth_text tokens present in extracted content.
- 166 rows excluded from dataset (had errors, missing truth_text, or were PDFs).
- 69 URLs confirmed dead via HEAD check and excluded from all metrics.
- Failure reasons recorded per URL in results.csv (`failure_reason` column).

## Raw results

See `results.csv` for per-URL breakdown.
