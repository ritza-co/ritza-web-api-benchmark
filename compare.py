"""
Head-to-head comparison of firecrawl/results.csv and tavily/results.csv.

A URL is treated as dead only if neither tool returned content and a HEAD check
marked it dead. Each tool only HEAD-checks its own failures, so excluding every
URL one tool called dead would also drop pages the other tool scraped fine.

Run: python3 compare.py
"""

import csv
import os

ROOT = os.path.dirname(__file__)


def load(tool):
    with open(os.path.join(ROOT, tool, "results.csv"), newline="", encoding="utf-8") as f:
        return {row["id"]: row for row in csv.DictReader(f)}


def percentile(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * p))]


def main():
    fc, tv = load("firecrawl"), load("tavily")
    assert fc.keys() == tv.keys(), "results.csv files cover different URLs"

    dead = {
        i for i in fc
        if fc[i]["success"] != "True" and tv[i]["success"] != "True"
        and "dead" in (fc[i]["failure_reason"], tv[i]["failure_reason"])
    }
    ids = [i for i in fc if i not in dead]

    print(f"URLs: {len(fc)}, dead: {len(dead)}, scored: {len(ids)}\n")
    print("| Metric | Firecrawl /scrape | Tavily /extract |")
    print("|---|---|---|")

    rows = {}
    for name, results in (("fc", fc), ("tv", tv)):
        scored = [results[i] for i in ids]
        successes = [r for r in scored if r["success"] == "True"]
        latencies = [float(r["latency_ms"]) for r in successes if float(r["latency_ms"]) < 30000]
        rows[name] = {
            "Content returned": f"{len(successes) / len(scored):.1%}",
            "Coverage": f"{sum(r['coverage'] == 'True' for r in scored) / len(scored):.1%}",
            "Recall": f"{sum(float(r['recall']) for r in scored) / len(scored):.3f}",
            "Recall (successful URLs)": f"{sum(float(r['recall']) for r in successes) / len(successes):.3f}",
            "P50 latency (ms)": f"{percentile(latencies, 0.5):,.0f}",
            "P95 latency (ms)": f"{percentile(latencies, 0.95):,.0f}",
            "$/URL": f"${sum(float(r['cost_usd']) for r in scored) / len(scored):.4f}",
        }
    for metric in rows["fc"]:
        print(f"| {metric} | {rows['fc'][metric]} | {rows['tv'][metric]} |")

    both = [i for i in ids if fc[i]["success"] == "True" and tv[i]["success"] == "True"]
    fc_only = sum(fc[i]["success"] == "True" and tv[i]["success"] != "True" for i in ids)
    tv_only = sum(tv[i]["success"] == "True" and fc[i]["success"] != "True" for i in ids)
    fc_both = sum(float(fc[i]["recall"]) for i in both) / len(both)
    tv_both = sum(float(tv[i]["recall"]) for i in both) / len(both)
    print(f"\nBoth returned content: {len(both)} URLs (recall: Firecrawl {fc_both:.3f}, Tavily {tv_both:.3f})")
    print(f"Only Firecrawl returned content: {fc_only}. Only Tavily: {tv_only}.")


if __name__ == "__main__":
    main()
