"""
Firecrawl v2 /scrape eval against firecrawl/scrape-content-dataset-v1.

Scoring:
- Coverage: retrieved at least 10% of truth_text tokens
- Recall: fraction of truth_text tokens present in retrieved content (primary quality metric)

Failure classification:
- "blocked"    — HTTP 403/429 anti-bot wall
- "dead"       — HTTP 4xx/5xx or connection error; URL is broken
- "timeout"    — request timed out
- "no_content" — API returned a result but markdown was empty

API errors are recorded in the api_error column. The run stops on HTTP 402
(out of credits) instead of recording empty results.

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
API_KEY = os.environ["FIRECRAWL_API_KEY"]
SCRAPE_URL = "https://api.firecrawl.dev/v2/scrape"
CREDITS_URL = "https://api.firecrawl.dev/v2/team/credit-usage"

# Stop before the balance drops below this, so a plan with a payment method on
# file never auto-upgrades. Must exceed the worst-case cost of one request.
MIN_CREDITS = int(os.environ.get("FIRECRAWL_MIN_CREDITS", 120))
# PDF URLs are excluded, but an extensionless URL can still serve a PDF, which
# costs 1 credit per page. Cap pages so one request can't exceed MIN_CREDITS.
PDF_MAX_PAGES = 100

# Free plan allows 10 /scrape requests per minute.
MIN_INTERVAL_S = 6.5

# Hobby plan billed monthly: $19 for 5,000 credits, 1 credit per scrape.
COST_PER_URL = 0.0038

RESULTS_FIELDS = [
    "id", "url", "success", "coverage", "recall",
    "latency_ms", "credits_used", "cost_usd",
    "content_length", "truth_length", "failure_reason", "api_error",
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


class OutOfCredits(Exception):
    pass


def scrape(session, url):
    """Return (markdown, api_error, latency_ms). Retries on 429; raises OutOfCredits on 402."""
    while True:
        start = time.time()
        try:
            resp = session.post(
                SCRAPE_URL,
                json={
                    "url": url,
                    "formats": ["markdown"],
                    "onlyMainContent": True,
                    "timeout": 60000,
                    # Force a live fetch so latency isn't flattered by Firecrawl's cache.
                    "maxAge": 0,
                    "parsers": [{"type": "pdf", "maxPages": PDF_MAX_PAGES}],
                },
                timeout=90,
            )
        except requests.exceptions.Timeout:
            return "", "timeout", (time.time() - start) * 1000
        except requests.exceptions.RequestException as e:
            return "", f"request_error: {e}", (time.time() - start) * 1000
        latency_ms = (time.time() - start) * 1000
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 30))
            print(f"(rate limited, sleeping {wait}s)", end=" ", flush=True)
            time.sleep(wait)
            continue
        if resp.status_code == 402:
            raise OutOfCredits(resp.text)
        try:
            body = resp.json()
        except ValueError:
            return "", f"http_{resp.status_code}", latency_ms
        if resp.status_code != 200 or not body.get("success"):
            return "", f"http_{resp.status_code}: {body.get('error', '')}"[:300], latency_ms
        return body.get("data", {}).get("markdown") or "", "", latency_ms


def remaining_credits(session):
    resp = session.get(CREDITS_URL, timeout=30)
    resp.raise_for_status()
    return resp.json()["data"]["remainingCredits"]


def is_pdf(url):
    return url.lower().split("?")[0].endswith(".pdf")


def load_dataset():
    # PDFs are excluded: this benchmark compares HTML page extraction, and
    # Firecrawl bills PDFs per page, which makes their cost unbounded.
    rows = []
    with open(DATASET_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row["error"] and row["truth_text"] and not is_pdf(row["url"]):
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

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {API_KEY}"})

    for i, row in enumerate(todo):
        url = row["url"]
        truth = row["truth_text"]
        print(f"[{i+1}/{len(todo)}] {url[:80]}", end=" ... ", flush=True)

        credits = remaining_credits(session)
        if credits < MIN_CREDITS:
            print(f"\n{credits} credits left (minimum {MIN_CREDITS}), stopping.")
            return

        start = time.time()
        try:
            content, api_error, latency_ms = scrape(session, url)
        except OutOfCredits as e:
            print(f"\nOut of credits, stopping: {e}")
            return

        success = bool(content)

        if success:
            failure_reason = ""
        elif "timeout" in api_error.lower():
            failure_reason = "timeout"
        else:
            failure_reason = classify_dead_url(url)
            if failure_reason == "alive":
                failure_reason = "no_content"

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
            "api_error": api_error,
        }
        append_result(result)

        if success:
            print(f"recall={rec:.3f} latency={latency_ms:.0f}ms")
        else:
            print(f"FAIL ({failure_reason})")

        time.sleep(max(0, MIN_INTERVAL_S - (time.time() - start)))

    print(f"\nDone. Run gen_readme.py to regenerate README.md.")


if __name__ == "__main__":
    main()
