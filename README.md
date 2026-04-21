# ritza-web-api-benchmark

Independent benchmark comparing Firecrawl `/scrape` and Tavily `/extract` on 848 real-world URLs. Written to accompany the article [Firecrawl vs. Tavily: Which Web Data API Should You Use?](https://techstackups.com/firecrawl-vs-tavily).

## Results summary

Both tools were tested against the [`firecrawl/scrape-content-dataset-v1`](https://huggingface.co/datasets/firecrawl/scrape-content-dataset-v1) dataset (1000 URLs, 848 usable). Dead URLs are excluded from all metrics.

| Metric | Firecrawl /scrape | Tavily /extract |
|---|---|---|
| Coverage (Success Rate) | 62.2% | 84.1% |
| Quality (Recall) | 0.489 | 0.650 |
| P50 Latency (ms) | 8,041 | 334 |
| P95 Latency (ms) | 30,000 | 1,481 |
| $/URL | $0.0063 | $0.0013 |

Coverage = at least 10% of ground-truth tokens retrieved. Recall = fraction of ground-truth tokens present in the response.

See `firecrawl/README.md` and `tavily/README.md` for full per-tool breakdowns.

## Dataset

Source: [`firecrawl/scrape-content-dataset-v1`](https://huggingface.co/datasets/firecrawl/scrape-content-dataset-v1) on HuggingFace. Published by Firecrawl. The dataset contains 1000 URLs with a `truth_text` ground-truth snippet for each page. 152 rows were excluded due to missing `truth_text` or dataset errors, leaving 848 usable URLs.

To download the dataset:

```bash
python3 download_dataset.py
```

This saves `dataset.csv` to the repo root. It is gitignored because the file is large (the original source on HuggingFace is the authoritative copy).

## Running the evals

### Setup

```bash
pip install firecrawl-py requests
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

Both evals resume from `results.csv` if interrupted. Delete `results.csv` to start fresh.

## Scoring methodology

**Coverage** -- whether at least 10% of the ground-truth tokens appeared in the retrieved content. A binary pass/fail per URL.

**Recall** -- the fraction of ground-truth tokens present in the retrieved content. Higher is better. We use recall rather than F1 because both tools return full pages that are longer than the short ground-truth snippet. F1 penalises precision and would unfairly score down tools that return more context.

**Dead URL handling** -- URLs confirmed unreachable via HEAD check (HTTP 4xx/5xx or connection error) are excluded from all metrics. No scraper can retrieve a broken page. Blocked URLs (403/429) are included because bypassing anti-bot walls is a meaningful product differentiator.

## Repository structure

```
.
+-- download_dataset.py     # downloads dataset.csv from HuggingFace
+-- dataset.csv             # gitignored -- download with download_dataset.py
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
