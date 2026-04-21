"""
Tavily /extract eval against firecrawl/scrape-content-dataset-v1.

Scoring:
- Coverage: retrieved at least 10% of truth_text tokens
- Recall: fraction of truth_text tokens present in retrieved content (primary quality metric)

Failure classification:
- "blocked"  — HTTP 403/429; anti-bot wall, no scraper guaranteed to succeed
- "dead"     — HTTP 4xx/5xx or connection error; URL is broken
- "timeout"  — Tavily timed out on this batch
- "no_content" — Tavily returned a result object but raw_content was empty

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

import requests

DATASET_PATH = os.path.join(os.path.dirname(__file__), "../dataset.csv")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results.csv")
README_PATH = os.path.join(os.path.dirname(__file__), "README.md")
API_KEY = os.environ["TAVILY_API_KEY"]

BATCH_SIZE = 5
COST_PER_CREDIT = 0.008
CREDITS_PER_BATCH = 1

RESULTS_FIELDS = [
    "id", "url", "success", "coverage", "recall",
    "latency_ms", "credits_used", "cost_usd",
    "content_length", "truth_length", "failure_reason",
]

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


def classify_dead_url(url):
    """HEAD-check a URL. Returns 'blocked', 'dead', or 'alive'."""
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
    ret_tokens = Counter(tokenize(retrieved))
    common = sum((ret_tokens & tru_tokens).values())
    return common / sum(tru_tokens.values())


def compute_coverage(retrieved, truth):
    if not retrieved or not truth:
        return False
    truth_tokens = set(tokenize(truth))
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


def load_all_results():
    if not os.path.exists(RESULTS_PATH):
        return []
    with open(RESULTS_PATH, newline="", encoding="utf-8") as f:
        return [
            {
                "coverage": row["coverage"] == "True",
                "recall": float(row["recall"]),
                "latency_ms": float(row["latency_ms"]),
                "cost_usd": float(row["cost_usd"]),
                "success": row["success"] == "True",
                "failure_reason": row.get("failure_reason", ""),
            }
            for row in csv.DictReader(f)
        ]


def main():
    print("Loading dataset...")
    dataset = load_dataset()
    print(f"Usable rows: {len(dataset)}")

    completed = load_completed_ids()
    print(f"Already completed: {len(completed)}")

    todo = [r for r in dataset if r["id"] not in completed]
    print(f"Remaining: {len(todo)}")

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {API_KEY}"})
    all_results = load_all_results()

    batches = [todo[i:i + BATCH_SIZE] for i in range(0, len(todo), BATCH_SIZE)]

    for batch_num, batch in enumerate(batches):
        urls = [row["url"] for row in batch]
        print(f"Batch {batch_num + 1}/{len(batches)} ({len(urls)} URLs)...", end=" ", flush=True)

        start = time.time()
        try:
            resp = session.post(
                "https://api.tavily.com/extract",
                json={"urls": urls, "extract_depth": "basic", "include_usage": True},
                timeout=30,
            )
            latency_ms = (time.time() - start) * 1000
            resp.raise_for_status()
            data = resp.json()

            content_by_url = {
                item["url"]: item.get("raw_content", "")
                for item in data.get("results", [])
            }
            # failed_results tells us which URLs Tavily explicitly rejected
            tavily_failed = {
                item["url"]: item.get("error", "")
                for item in data.get("failed_results", [])
            }
            credits_used = data.get("usage", {}).get("credits", CREDITS_PER_BATCH)
            batch_api_error = None
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            content_by_url = {}
            tavily_failed = {}
            credits_used = CREDITS_PER_BATCH
            batch_api_error = str(e)
            print(f"ERROR: {batch_api_error}")

        latency_per_url = latency_ms / len(urls)
        cost_per_url = (credits_used * COST_PER_CREDIT) / len(urls)

        batch_successes = 0
        for row in batch:
            url = row["url"]
            truth = row["truth_text"]
            content = content_by_url.get(url, "")
            success = bool(content)

            if success:
                batch_successes += 1
                failure_reason = ""
            elif batch_api_error:
                failure_reason = "timeout" if "timeout" in batch_api_error.lower() else f"api_error"
            elif url in tavily_failed:
                # Tavily told us it failed — classify by HEAD-checking the URL
                failure_reason = classify_dead_url(url)
            else:
                # Tavily returned a result object but raw_content was empty
                failure_reason = "no_content"

            cov = compute_coverage(content, truth) if success else False
            rec = compute_recall(content, truth) if success else 0.0

            result = {
                "id": row["id"],
                "url": url,
                "success": success,
                "coverage": cov,
                "recall": round(rec, 4),
                "latency_ms": round(latency_per_url, 1),
                "credits_used": credits_used,
                "cost_usd": round(cost_per_url, 6),
                "content_length": len(content),
                "truth_length": len(truth),
                "failure_reason": failure_reason,
            }
            append_result(result)
            all_results.append({
                "coverage": cov,
                "recall": rec,
                "latency_ms": latency_per_url,
                "cost_usd": cost_per_url,
                "success": success,
                "failure_reason": failure_reason,
            })

        print(f"OK {batch_successes}/{len(batch)}, latency {latency_ms:.0f}ms, credits {credits_used}")

        if batch_num < len(batches) - 1:
            time.sleep(0.3)

    total_cost = sum(r["cost_usd"] for r in all_results)
    print(f"\nDone. Estimated total cost: ${total_cost:.4f}")
    print("Run gen_readme.py to regenerate README.md from results.")


if __name__ == "__main__":
    main()
