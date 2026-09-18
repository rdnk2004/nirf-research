"""
Step 2 of the Scopus pipeline: pull publication + citation data for each
confirmed AF-ID, per year.

Mirrors the NIRF scraper's design principles: cached (resumable), rate
limited, fails per institution-year rather than crashing the whole run,
and writes incrementally so a crash or quota exhaustion partway through
doesn't lose completed work.

Input:
    output/af_id_candidates.csv, after you've manually put "yes" in the
    `confirmed` column for the correct affilname per institution (see
    affiliation_lookup.py's output). Despite the filename, this holds
    affilname strings, not numeric AF-IDs -- Scopus's numeric AF-ID isn't
    available at this key's access tier, confirmed by inspecting a real
    API response, so this pipeline matches institutions by their exact
    Scopus affiliation-name string instead (AFFIL("...") queries).

Output:
    output/scopus_raw_documents.csv   -- one row per paper
    output/scopus_yearly_summary.csv  -- one row per institution-year:
                                          total_documents, total_citations,
                                          avg_citations_per_doc
    output/scopus_failures.log

Usage:
    python3 scopus_scraper.py --years 2021 2022 2023 2024 2025
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("SCOPUS_API_KEY")
INST_TOKEN = os.getenv("SCOPUS_INST_TOKEN") or None
BASE_DELAY = 1.0
PAGE_SIZE = 25  # conservative default for STANDARD view; raise if your tier allows more
RESULT_WINDOW_CEILING = 5000  # Scopus's typical offset-pagination ceiling

CACHE_DIR = Path("cache/scopus")
OUTPUT_DIR = Path("output")
DOCS_CSV = OUTPUT_DIR / "scopus_raw_documents.csv"
SUMMARY_CSV = OUTPUT_DIR / "scopus_yearly_summary.csv"
FAIL_LOG = OUTPUT_DIR / "scopus_failures.log"

HEADERS = {"X-ELS-APIKey": API_KEY, "Accept": "application/json"}
if INST_TOKEN:
    HEADERS["X-ELS-Insttoken"] = INST_TOKEN

DOC_FIELDS = [
    "institute_id", "year", "scopus_id", "title", "journal",
    "issn", "eissn", "cover_date", "citedby_count", "doc_type", "aggregation_type",
]
SUMMARY_FIELDS = [
    "institute_id", "year", "total_documents", "total_citations",
    "avg_citations_per_doc", "note",
]


def load_confirmed_affiliations(path: str) -> dict:
    mapping = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("confirmed", "").strip().lower() == "yes":
                mapping[row["institute_id"]] = {
                    "affilname": row["affilname"],
                    "name": row["nirf_name"],
                }
    return mapping


def fetch_page(affilname: str, year: int, start: int, cache_key: str) -> dict | None:
    cache_path = CACHE_DIR / f"{cache_key}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    time.sleep(BASE_DELAY)
    query = f'AFFIL("{affilname}") AND PUBYEAR = {year}'
    try:
        resp = requests.get(
            "https://api.elsevier.com/content/search/scopus",
            headers=HEADERS,
            params={"query": query, "count": PAGE_SIZE, "start": start, "view": "STANDARD"},
            timeout=30,
        )
    except requests.RequestException as e:
        print(f"    Request error: {e}")
        return None

    remaining = resp.headers.get("X-RateLimit-Remaining")
    if remaining is not None and remaining.isdigit() and int(remaining) < 10:
        print(f"    WARNING: only {remaining} API calls left on this key's quota window.")

    if resp.status_code == 429:
        print("    Rate limited -- waiting 30s...")
        time.sleep(30)
        return fetch_page(affilname, year, start, cache_key)  # retry once after backoff

    if resp.status_code != 200:
        print(f"    HTTP {resp.status_code}: {resp.text[:200]}")
        return None

    data = resp.json()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(data), encoding="utf-8")
    return data


def parse_entries(entries: list, institute_id: str, year: int) -> list[dict]:
    rows = []
    for e in entries:
        rows.append({
            "institute_id": institute_id,
            "year": year,
            "scopus_id": e.get("dc:identifier", "").replace("SCOPUS_ID:", ""),
            "title": e.get("dc:title", ""),
            "journal": e.get("prism:publicationName", ""),
            "issn": e.get("prism:issn", ""),
            "eissn": e.get("prism:eIssn", ""),
            "cover_date": e.get("prism:coverDate", ""),
            "citedby_count": e.get("citedby-count", "0"),
            "doc_type": e.get("subtypeDescription", ""),
            "aggregation_type": e.get("prism:aggregationType", ""),
        })
    return rows


def append_rows(path: Path, fieldnames: list, rows: list[dict]):
    write_header = not path.exists()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def already_done_institute_years() -> set:
    done = set()
    if SUMMARY_CSV.exists():
        with open(SUMMARY_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add((row["institute_id"], row["year"]))
    return done


def pull_institute_year(institute_id: str, af_id: str, year: int):
    all_entries = []
    start = 0
    total_results = None

    while True:
        cache_key = f"{institute_id}_{year}_{start}"
        data = fetch_page(af_id, year, start, cache_key)
        if data is None:
            with open(FAIL_LOG, "a", encoding="utf-8") as f:
                f.write(f"{institute_id}\t{year}\tstart={start}\tfetch_failed\n")
            break

        results = data.get("search-results", {})
        if total_results is None:
            total_results = int(results.get("opensearch:totalResults", "0"))
            if total_results > RESULT_WINDOW_CEILING:
                print(f"    NOTE: {total_results} total results exceeds the "
                      f"~{RESULT_WINDOW_CEILING} pagination ceiling -- some "
                      f"records past that point may be unreachable via offset "
                      f"pagination. Logged for your awareness.")
                with open(FAIL_LOG, "a", encoding="utf-8") as f:
                    f.write(f"{institute_id}\t{year}\ttotal={total_results}\texceeds_pagination_ceiling\n")

        entries = results.get("entry", [])
        if not entries or "error" in entries[0]:
            break

        all_entries.extend(entries)
        start += PAGE_SIZE
        if start >= min(total_results, RESULT_WINDOW_CEILING):
            break

    doc_rows = parse_entries(all_entries, institute_id, year)
    if doc_rows:
        append_rows(DOCS_CSV, DOC_FIELDS, doc_rows)

    total_docs = len(doc_rows)
    total_citations = sum(int(r["citedby_count"] or 0) for r in doc_rows)
    avg_citations = round(total_citations / total_docs, 2) if total_docs else 0

    note = ""
    if total_results and total_results > len(doc_rows):
        note = f"only {len(doc_rows)}/{total_results} retrieved (ceiling or partial failure)"

    append_rows(SUMMARY_CSV, SUMMARY_FIELDS, [{
        "institute_id": institute_id, "year": year,
        "total_documents": total_docs, "total_citations": total_citations,
        "avg_citations_per_doc": avg_citations, "note": note,
    }])

    print(f"    -> {total_docs} documents, {total_citations} total citations, "
          f"{avg_citations} avg/doc" + (f"  [{note}]" if note else ""))


def main(years: list[int], affiliation_csv: str):
    if not API_KEY:
        print("ERROR: SCOPUS_API_KEY not set in .env")
        sys.exit(1)

    affiliations = load_confirmed_affiliations(affiliation_csv)
    if not affiliations:
        print(f"ERROR: no rows with confirmed='yes' found in {affiliation_csv}")
        print("Fill in the 'confirmed' column first (see affiliation_lookup.py output).")
        sys.exit(1)

    done = already_done_institute_years()
    print(f"{len(affiliations)} confirmed institutions, {len(years)} years.\n")

    for institute_id, info in affiliations.items():
        for year in years:
            if (institute_id, str(year)) in done:
                continue
            print(f"[{info['name']}] {year} (AF-ID {info['af_id']})")
            pull_institute_year(institute_id, info["af_id"], year)

    print(f"\nDone. Per-document data: {DOCS_CSV}")
    print(f"Per-institution-year summary: {SUMMARY_CSV}")
    print(f"Check {FAIL_LOG} for anything that needs attention.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, nargs="+", required=True)
    parser.add_argument("--affiliations", default="output/af_id_candidates.csv",
                         help="Path to the confirmed AF-ID CSV")
    args = parser.parse_args()
    main(args.years, args.affiliations)