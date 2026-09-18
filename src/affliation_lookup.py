"""
Step 1 of the Scopus pipeline: find each university's Scopus AF-ID.

IMPORTANT: this does NOT call the separate Affiliation Search API. A first
version did, and it returned 401 AUTHORIZATION_ERROR -- that endpoint is
gated separately from the core Scopus Search API and isn't covered by this
key's entitlement, even though Search itself works fine. Instead, this
searches AFFIL("<name>") against the Search API and counts which AF-ID
appears most often across a sample of real matching documents.

This does NOT auto-pick an AF-ID -- Indian universities frequently have
multiple Scopus affiliation records (main campus vs. constituent colleges,
old vs. renamed entities, sometimes genuine duplicates in Scopus's own
data). Picking the wrong one silently corrupts every downstream number.
This script surfaces up to 5 candidates per institution with enough
context (name, city, country, how often it appeared in the sample) for
you to confirm the right one by hand.

Input:
    A CSV with at least: institute_id, name (or name_canonical)
    -- e.g. your cleaned NIRF output, nirf_university_raw_clean.csv

Output:
    output/af_id_candidates.csv -- one row per candidate, grouped by
    institute_id, with a blank `confirmed` column for you to fill in
    (put "yes" in the row you're confirming as correct).

Usage:
    python3 affiliation_lookup.py path/to/nirf_university_raw_clean.csv
"""

import csv
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("SCOPUS_API_KEY")
INST_TOKEN = os.getenv("SCOPUS_INST_TOKEN") or None
BASE_DELAY = 1.0
OUTPUT_PATH = "output/af_id_candidates.csv"

HEADERS = {"X-ELS-APIKey": API_KEY, "Accept": "application/json"}
if INST_TOKEN:
    HEADERS["X-ELS-Insttoken"] = INST_TOKEN


def search_affiliation(name: str, retries: int = 3) -> list[dict]:
    """
    Finds candidate AF-IDs WITHOUT using the separate Affiliation Search API
    (that endpoint returned 401 AUTHORIZATION_ERROR -- it's gated separately
    from the core Scopus Search API and evidently isn't in this key's
    entitlement). Instead, this searches AFFIL("<name>") against the Search
    API (confirmed working) and counts which AF-ID appears most often across
    a sample of real matching documents -- arguably a more reliable signal
    than a bare name lookup, since it's grounded in actual papers.
    """
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                "https://api.elsevier.com/content/search/scopus",
                headers=HEADERS,
                params={
                    "query": f'AFFIL("{name}")',
                    "count": 25,
                    "view": "STANDARD",
                },
                timeout=30,
            )
        except requests.RequestException as e:
            print(f"  Request error ({e}), attempt {attempt}/{retries}")
            time.sleep(BASE_DELAY * attempt)
            continue

        if resp.status_code == 200:
            entries = resp.json().get("search-results", {}).get("entry", [])
            af_counter = {}  # af_id -> {"name":..., "city":..., "country":..., "count": N}
            for e in entries:
                if "error" in e:
                    continue
                affs = e.get("affiliation", [])
                if isinstance(affs, dict):  # sometimes a single dict instead of a list
                    affs = [affs]
                for aff in affs:
                    af_id = aff.get("afid", "")
                    if not af_id:
                        continue
                    if af_id not in af_counter:
                        af_counter[af_id] = {
                            "af_name": aff.get("affilname", ""),
                            "city": aff.get("affiliation-city", ""),
                            "country": aff.get("affiliation-country", ""),
                            "count": 0,
                        }
                    af_counter[af_id]["count"] += 1

            # rank by how often this AF-ID showed up among matching documents
            ranked = sorted(af_counter.items(), key=lambda kv: -kv[1]["count"])
            candidates = [
                {
                    "af_id": af_id,
                    "af_name": info["af_name"],
                    "city": info["city"],
                    "country": info["country"],
                    "doc_count": f"{info['count']}/{len(entries)} sampled docs",
                }
                for af_id, info in ranked[:5]
            ]
            return candidates
        elif resp.status_code == 429:
            print("  Rate limited, backing off...")
            time.sleep(5 * attempt)
        elif resp.status_code == 401:
            print(f"  HTTP 401: {resp.text[:200]}")
            print("  This means even the core Search API is now being denied --")
            print("  different from the earlier Affiliation-API-only 401. Stop and")
            print("  check your quota/key status on the Developer Portal before continuing.")
            return []
        else:
            print(f"  HTTP {resp.status_code}: {resp.text[:200]}")
            time.sleep(BASE_DELAY * attempt)
    return []


def main(input_csv: str):
    if not API_KEY:
        print("ERROR: SCOPUS_API_KEY not set in .env")
        sys.exit(1)

    with open(input_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        name_col = "name_canonical" if "name_canonical" in reader.fieldnames else "name"
        institutions = {}
        for row in reader:
            institutions[row["institute_id"]] = row[name_col]

    os.makedirs("output", exist_ok=True)
    rows_out = []

    for i, (institute_id, name) in enumerate(institutions.items(), 1):
        print(f"[{i}/{len(institutions)}] Looking up: {name}")
        candidates = search_affiliation(name)
        if not candidates:
            print(f"  NO CANDIDATES FOUND -- will need a manual search on scopus.com for this one")
            rows_out.append({
                "institute_id": institute_id, "nirf_name": name,
                "af_id": "", "af_name": "NOT FOUND -- search manually",
                "city": "", "country": "", "doc_count": "", "confirmed": "",
            })
        else:
            for c in candidates:
                rows_out.append({
                    "institute_id": institute_id, "nirf_name": name,
                    "af_id": c["af_id"], "af_name": c["af_name"],
                    "city": c["city"], "country": c["country"],
                    "doc_count": c["doc_count"], "confirmed": "",
                })
        time.sleep(BASE_DELAY)

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "institute_id", "nirf_name", "af_id", "af_name",
            "city", "country", "doc_count", "confirmed",
        ])
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"\nDone. {len(institutions)} institutions looked up.")
    print(f"Candidates written to: {OUTPUT_PATH}")
    print("\nNEXT STEP (manual, required):")
    print("  Open that CSV. For each institute_id, look at its candidate rows")
    print("  (city/country/doc_count help you tell them apart) and type 'yes'")
    print("  in the 'confirmed' column for the correct one. Leave the rest blank.")
    print("  Rows marked 'NOT FOUND' need a manual lookup at scopus.com --")
    print("  search Organizations there, find the right AF-ID, add it as a")
    print("  new row with confirmed='yes'.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 affiliation_lookup.py path/to/nirf_data.csv")
        sys.exit(1)
    main(sys.argv[1])