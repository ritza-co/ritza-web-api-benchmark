"""
Firecrawl /scrape eval against firecrawl/scrape-content-dataset-v1.

Scoring:
- Coverage: retrieved at least 10% of truth_text tokens
- Recall: fraction of truth_text tokens present in retrieved content (primary quality metric)

Failure classification:
- "blocked"    — HTTP 403/429 anti-bot wall
- "dead"       — HTTP 4xx/5xx or connection error; URL is broken
- "timeout"    — request timed out
- "no_content" — API returned a result but markdown was empty

Run: python3 eval.py
Resumes from results.csv if interrupted (skips already-processed IDs).
"""

import csv
import os
import ssl
import time
import urllib.error
import urllib.request
from collections import Counter

from firecrawl import V1FirecrawlApp

DATASET_PATH = os.path.join(os.path.dirname(__file__), "../dataset.csv")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results.csv")
API_KEY = os.environ["FIRECRAWL_API_KEY"]

COST_PER_URL = 0.0063

RESULTS_FIELDS = [
    "id", "url", "success", "coverage", "recall",
    "latency_ms", "credits_used", "cost_usd",
    "content_length", "truth_length", "failure_reason",
]

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


def classify_dead_url(url):
    try:
        req = urllib.request.Request(
            url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"}
        )
        resp = urllib.request.urlopen(req, timeout=6, context=_ssl_ctx)
        return "alive" if resp.status < 400 else "dead"
    except urllib.error.HTTPError as e:
        return "blocked" if e.code in (401, 403, 429) else "dead"
    except Exception:
        return "dead"


def tokenize(text):
    return text.lower().split()


def compute_recall(retrieved, truth):
    if not retrieved or not truth:
        return 0.0
    tru_tokens = Counter(tokenize(truth))
    if not tru_tokens:
        return 0.0
    ret_tokens = Counter(tokenize(retrieved))
    common = sum((ret_tokens & tru_tokens).values())
    return common / sum(tru_tokens.values())


def compute_coverage(retrieved, truth):
    if not retrieved or not truth:
        return False
    truth_tokens = set(tokenize(truth))
    if not truth_tokens:
        return False
    ret_tokens = set(tokenize(retrieved))
    return len(truth_tokens & ret_tokens) / len(truth_tokens) >= 0.10


def load_dataset():
    rows = []
    with open(DATASET_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row["error"] and row["truth_text"]:
                rows.append(row)
    return rows


def load_completed_ids():
    if not os.path.exists(RESULTS_PATH):
        return set()
    with open(RESULTS_PATH, newline="", encoding="utf-8") as f:
        return {row["id"] for row in csv.DictReader(f)}


def append_result(result):
    write_header = not os.path.exists(RESULTS_PATH)
    with open(RESULTS_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULTS_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(result)


def main():
    print("Loading dataset...")
    dataset = load_dataset()
    print(f"Usable rows: {len(dataset)}")

    completed = load_completed_ids()
    print(f"Already completed: {len(completed)}")

    todo = [r for r in dataset if r["id"] not in completed]
    print(f"Remaining: {len(todo)}")

    client = V1FirecrawlApp(api_key=API_KEY)

    for i, row in enumerate(todo):
        url = row["url"]
        truth = row["truth_text"]
        print(f"[{i+1}/{len(todo)}] {url[:80]}", end=" ... ", flush=True)

        start = time.time()
        try:
            response = client.scrape_url(
                url,
                formats=["markdown"],
                only_main_content=True,
                timeout=60000,
            )
            latency_ms = (time.time() - start) * 1000
            content = response.markdown or ""
            api_error = None
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            content = ""
            api_error = str(e)

        success = bool(content)

        if success:
            failure_reason = ""
        elif api_error and "timeout" in api_error.lower():
            failure_reason = "timeout"
        else:
            failure_reason = classify_dead_url(url)

        cov = compute_coverage(content, truth) if success else False
        rec = compute_recall(content, truth) if success else 0.0

        result = {
            "id": row["id"],
            "url": url,
            "success": success,
            "coverage": cov,
            "recall": round(rec, 4),
            "latency_ms": round(latency_ms, 1),
            "credits_used": 1,
            "cost_usd": COST_PER_URL,
            "content_length": len(content),
            "truth_length": len(truth),
            "failure_reason": failure_reason,
        }
        append_result(result)

        if success:
            print(f"recall={rec:.3f} latency={latency_ms:.0f}ms")
        else:
            print(f"FAIL ({failure_reason})")

        time.sleep(0.2)

    print(f"\nDone. Run gen_readme.py to regenerate README.md.")


if __name__ == "__main__":
    main()
