"""Download the Firecrawl scrape-content-dataset-v1 from HuggingFace and save as dataset.csv."""

import csv
import os
import urllib.request

URL = "https://huggingface.co/datasets/firecrawl/scrape-content-dataset-v1/resolve/main/1-0-0.csv"
OUT = os.path.join(os.path.dirname(__file__), "dataset.csv")

print(f"Downloading dataset to {OUT}...")
urllib.request.urlretrieve(URL, OUT)
print("Done.")

with open(OUT, newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

total = len(rows)
usable = sum(1 for r in rows if not r.get("error") and r.get("truth_text"))
print(f"Total rows: {total}")
print(f"Usable rows (no error, has truth_text): {usable}")
