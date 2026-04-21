# Firecrawl /scrape Eval Results

Dataset: `firecrawl/scrape-content-dataset-v1` (1000 URLs, 848 usable after filtering dataset errors)
Endpoint: Firecrawl `/scrape` (`only_main_content=True`, `formats=["markdown"]`)
Run date: 2026-04-21

## URL classification

| Status | Count | Included in metrics? |
|---|---|---|
| Content returned | 574 | Yes |
| No content -- blocked (403/429) | 56 | Yes -- bypassing anti-bot walls is a product differentiator |
| No content -- Firecrawl miss | 3 | Yes -- reachable pages Firecrawl failed to extract |
| Dead URL (confirmed unreachable) | 31 | No -- no scraper can retrieve a dead page |
| **Fair denominator** | **817** | |

## Results

Metrics calculated over 817 URLs (dead URLs excluded from denominator).

| Metric | This run |
|---|---|
| Coverage (Success Rate) | 62.2% |
| Quality (Recall) | 0.489 |
| P50 Latency (ms) | 1875 |
| P95 Latency (ms) | 6542 |
| $/URL | $0.0063 |

When Firecrawl successfully retrieved a page (n=574), recall was 0.697 and coverage was 88.5%.

## Methodology notes

- Each URL scraped individually via the Firecrawl `/scrape` endpoint.
- Cost calculated at $0.0063/URL (PAYG rate at time of testing).
- Latency computed over successful rows only. Rows exceeding 30,000ms excluded from P50/P95.
- Coverage = at least 10% of truth_text tokens present in extracted content.
- Recall = fraction of truth_text tokens present in extracted content (primary quality metric).
- 152 rows excluded from dataset (had errors or missing truth_text).
- 31 URLs confirmed dead via HEAD check and excluded from all metrics.
- Failure reasons recorded per URL in results.csv (`failure_reason` column).

## Raw results

See `results.csv` for per-URL breakdown.
