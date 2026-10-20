# Firecrawl /scrape Eval Results

Dataset: `firecrawl/scrape-content-dataset-v1` (1000 URLs, 834 usable after filtering dataset errors and PDFs)
Endpoint: Firecrawl v2 `/scrape` (`onlyMainContent=true`, `formats=["markdown"]`)
Run date: 2026-10-20

## URL classification

| Status | Count | Included in metrics? |
|---|---|---|
| Content returned | 803 | Yes |
| No content -- blocked (403/429) | 5 | Yes -- bypassing anti-bot walls is a product differentiator |
| No content -- Firecrawl miss | 12 | Yes -- reachable pages Firecrawl failed to extract |
| Dead URL (confirmed unreachable) | 14 | No -- no scraper can retrieve a dead page |
| **Fair denominator** | **820** | |

## Results

Metrics calculated over 820 URLs (dead URLs excluded from denominator).

| Metric | This run |
|---|---|
| Coverage (Success Rate) | 84.1% |
| Quality (Recall) | 0.636 |
| P50 Latency (ms) | 2829 |
| P95 Latency (ms) | 11086 |
| $/URL | $0.0038 |

When Firecrawl successfully retrieved a page (n=803), recall was 0.649 and coverage was 85.9%.

## Methodology notes

- Each URL scraped individually via the Firecrawl v2 `/scrape` endpoint with `maxAge=0` (live fetch, no cache).
- Cost calculated at $0.0038/URL (Hobby plan billed monthly: $19 for 5,000 credits).
- Latency computed over successful rows only. Rows exceeding 30,000ms excluded from P50/P95.
- Coverage = at least 10% of truth_text tokens present in extracted content.
- Recall = fraction of truth_text tokens present in extracted content (primary quality metric).
- 166 rows excluded from dataset (had errors, missing truth_text, or were PDFs).
- 14 URLs confirmed dead via HEAD check and excluded from all metrics.
- Failure reasons recorded per URL in results.csv (`failure_reason` column).

## Raw results

See `results.csv` for per-URL breakdown.
