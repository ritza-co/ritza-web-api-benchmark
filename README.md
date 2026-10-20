# ritza-web-api-benchmark

Independent benchmark comparing Firecrawl `/scrape` and Tavily `/extract` on 848 real-world URLs. Written to accompany the article [Firecrawl vs. Tavily: Which Web Data API Should You Use?](https://techstackups.com/comparisons/firecrawl-vs-tavily/).

## Results summary

Re-run on 2026-10-20 against Firecrawl's v2 API. The first run (April 2026) ran out of Firecrawl free credits after 586 URLs, and the remaining 262 empty responses were scored as failures. This run stops when credits run low instead of recording empty results.

Both tools were tested against the [`firecrawl/scrape-content-dataset-v1`](https://huggingface.co/datasets/firecrawl/scrape-content-dataset-v1) dataset (1000 URLs, 834 usable). 13 dead URLs are excluded from all metrics, leaving 821 scored URLs.

| Metric | Firecrawl /scrape | Tavily /extract |
|---|---|---|
| Content returned | 97.8% | 73.4% |
| Coverage | 84.0% | 68.5% |
| Recall | 0.635 | 0.506 |
| Recall (successful URLs) | 0.649 | 0.689 |
| P50 latency (ms) | 2,829 | 538 |
| P95 latency (ms) | 11,086 | 1,626 |
| $/URL | $0.0038 | $0.0012 |

On the 596 URLs where both tools returned content, recall was 0.718 for Firecrawl and 0.688 for Tavily. Firecrawl returned content on 207 URLs where Tavily returned none. Tavily returned content on 7 URLs where Firecrawl returned none.

Coverage = at least 10% of ground-truth tokens retrieved. Recall = fraction of ground-truth tokens present in the response.

Tavily latency is per batch of 5 URLs divided by 5, so it is not directly comparable to Firecrawl's single-URL latency. Firecrawl was run with `maxAge=0` to force a live fetch rather than a cached result.

Cost per URL uses each tool's entry pricing: Firecrawl Hobby billed monthly ($19 for 5,000 credits, 1 credit per page) and Tavily pay-as-you-go ($0.008 per credit, 1 credit per 5 URLs).

Run `python3 compare.py` to regenerate this table. See `firecrawl/README.md` and `tavily/README.md` for per-tool breakdowns.

## Dataset

Source: [`firecrawl/scrape-content-dataset-v1`](https://huggingface.co/datasets/firecrawl/scrape-content-dataset-v1) on HuggingFace. Published by Firecrawl. The dataset contains 1000 URLs with a `truth_text` ground-truth snippet for each page. 152 rows were excluded due to missing `truth_text` or dataset errors, and 14 PDF URLs were excluded because this benchmark compares HTML page extraction (Firecrawl also bills PDFs per page), leaving 834 usable URLs.

To download the dataset:

```bash
python3 download_dataset.py
```

This saves `dataset.csv` to the repo root. It is gitignored because the file is large (the original source on HuggingFace is the authoritative copy).

## Running the evals

### Setup

```bash
pip install requests
cp .env.example .env
# edit .env and add your API keys
```

Get your keys from:
- Firecrawl: https://www.firecrawl.dev
- Tavily: https://app.tavily.com

### Firecrawl

```bash
cd firecrawl
export $(cat ../.env | xargs)
python3 eval.py
python3 gen_readme.py
```

### Tavily

```bash
cd tavily
export $(cat ../.env | xargs)
python3 eval.py
python3 gen_readme.py
```

### Comparison

```bash
python3 compare.py
```

Both evals resume from `results.csv` if interrupted. Delete `results.csv` to start fresh.

The Firecrawl eval checks the remaining credit balance before every request and stops below `FIRECRAWL_MIN_CREDITS` (default 120). This prevents empty results when credits run out, and prevents an automatic plan upgrade on accounts with a payment method.

## Scoring methodology

**Coverage** -- whether at least 10% of the ground-truth tokens appeared in the retrieved content. A binary pass/fail per URL.

**Recall** -- the fraction of ground-truth tokens present in the retrieved content. Higher is better. We use recall rather than F1 because both tools return full pages that are longer than the short ground-truth snippet. F1 penalises precision and would unfairly score down tools that return more context.

**Dead URL handling** -- a URL is excluded from all metrics only if neither tool returned content and a HEAD check (HTTP 4xx/5xx or connection error) marked it dead. No scraper can retrieve a broken page. Blocked URLs (403/429) are included because bypassing anti-bot walls is a meaningful product differentiator. The per-tool READMEs exclude each tool's own dead URLs, so their numbers differ slightly from the head-to-head table.

## Repository structure

```
.
+-- download_dataset.py     # downloads dataset.csv from HuggingFace
+-- dataset.csv             # gitignored -- download with download_dataset.py
+-- compare.py              # head-to-head table from both results.csv files
+-- firecrawl/
|   +-- eval.py             # runs Firecrawl /scrape against the dataset
|   +-- gen_readme.py       # generates firecrawl/README.md from results.csv
|   +-- results.csv         # our results (included for reproducibility)
|   +-- README.md           # generated results summary
+-- tavily/
    +-- eval.py             # runs Tavily /extract against the dataset
    +-- gen_readme.py       # generates tavily/README.md from results.csv
    +-- results.csv         # our results (included for reproducibility)
    +-- README.md           # generated results summary
```
