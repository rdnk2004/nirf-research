"""
Step 2 of the Scopus pipeline: pull publication + citation data for each
confirmed AF-ID, per year.

Mirrors the NIRF scraper's design principles: cached (resumable), rate
limited, fails per institution-year rather than crashing the whole run,
and writes incrementally so a crash or quota exhaustion partway through
doesn't lose completed work.

Input:
    data/reference/af_id_candidates_confirmed.csv, after you've manually put "yes" in the
    `confirmed` column for the correct affilname per institution (see
    affiliation_lookup.py's output). Despite the filename, this holds
    affilname strings, not numeric AF-IDs -- Scopus's numeric AF-ID isn't
    available at this key's access tier, confirmed by inspecting a real
    API response, so this pipeline matches institutions by their exact
    Scopus affiliation-name string instead (AFFIL("...") queries).

Output:
    data/pipeline/scopus_raw_documents.csv   -- one row per paper
    data/pipeline/scopus_yearly_summary.csv  -- one row per institution-year:
                                          total_documents, total_citations,
                                          avg_citations_per_doc
    data/pipeline/scopus_failures.log

Usage:
    python3 scopus_scraper.py --years 2021 2022 2023 2024 2025
"""

import argparse
import csv
import hashlib
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
OUTPUT_DIR = Path("data/pipeline")
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


def _is_ceiling_note(note: str) -> bool:
    """True for both the current 'CEILING: ...' note format and the
    legacy 'only X/Y retrieved (ceiling or partial failure)' phrasing
    used before this distinction existed -- rows already written to
    scopus_yearly_summary.csv from earlier runs use the old phrasing, and
    must still be recognized as finished, not newly misclassified as
    needing a pointless retry."""
    return note.startswith("CEILING:") or "ceiling" in note.lower()


def already_done_institute_years() -> set:
    """
    Counts an institute-year as done (skip entirely, no purge, no retry)
    if it completed cleanly (no note) OR hit the pagination ceiling --
    a ceiling result is already the maximum obtainable, so it is treated
    as finished, not "partial". Only a genuine fetch-failure note (see
    partial_institute_years below) means real retry is worthwhile.
    """
    done = set()
    if SUMMARY_CSV.exists():
        with open(SUMMARY_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                note = row.get("note", "").strip()
                if not note or _is_ceiling_note(note):
                    done.add((row["institute_id"], row["year"]))
    return done


def partial_institute_years() -> set:
    """(institute_id, year) pairs that exist but have a genuine
    fetch-failure note -- these need a clean, purged retry. Ceiling rows
    (current or legacy phrasing) are deliberately excluded here: retrying
    them wastes time for an identical result every time."""
    partial = set()
    if SUMMARY_CSV.exists():
        with open(SUMMARY_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                note = row.get("note", "").strip()
                if note and not _is_ceiling_note(note):
                    partial.add((row["institute_id"], str(row["year"])))
    return partial


def purge_institute_year(path: Path, fieldnames: list, institute_id: str, year: int, retries: int = 3):
    """
    Removes all existing rows for one institute-year from a CSV before a
    retry re-appends fresh ones -- otherwise a retry after a partial
    failure would duplicate every row that succeeded the first time
    around, on top of the freshly (and now hopefully complete) fetched set.

    Retries on OSError: on Windows, a file can be transiently locked by
    antivirus scanning, OneDrive/cloud sync, or simply being open in
    Excel -- a brief wait and retry handles this without losing the run.
    """
    if not path.exists():
        return
    for attempt in range(1, retries + 1):
        try:
            with open(path, newline="", encoding="utf-8") as f:
                rows = [r for r in csv.DictReader(f)
                        if not (r["institute_id"] == institute_id and str(r["year"]) == str(year))]
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            return
        except OSError as e:
            print(f"    File access error on {path.name} (attempt {attempt}/{retries}): {e}")
            print(f"    If this keeps happening, check whether {path} is open in Excel or")
            print(f"    another program, or being synced by OneDrive/cloud storage.")
            time.sleep(2 * attempt)
    raise OSError(f"Could not access {path} after {retries} attempts -- see messages above.")


def pull_institute_year(institute_id: str, affilname: str, year: int):
    all_entries = []
    start = 0
    total_results = None
    fetch_failed = False

    while True:
        # Include a short hash of the affilname in the cache key -- NOT
        # just institute_id/year/page. Without this, correcting a wrong
        # affilname and retrying would silently return the OLD cached
        # response from the wrong name's query, since institute_id and
        # year alone don't change when only the search name is fixed.
        # This is exactly what caused NMIMS and Mahatma Gandhi University
        # to still show 0 results after their names were corrected.
        name_hash = hashlib.md5(affilname.encode("utf-8")).hexdigest()[:8]
        cache_key = f"{institute_id}_{year}_{name_hash}_{start}"
        data = fetch_page(affilname, year, start, cache_key)
        if data is None:
            fetch_failed = True
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
    if fetch_failed:
        # A network/API failure happened during this pull -- even if it hit
        # on the very first page (so total_results was never confirmed),
        # this must NOT be left indistinguishable from a genuine
        # zero-output institution. An empty note here is what caused
        # earlier connection failures to be silently treated as "done"
        # forever.
        note = (f"fetch failed at start={start} -- only {len(doc_rows)}"
                f"/{total_results if total_results is not None else '?'} retrieved, needs retry")
    elif total_results and total_results > len(doc_rows):
        # Hit Scopus's offset-pagination ceiling (RESULT_WINDOW_CEILING),
        # not a failure. This is the maximum obtainable via this API --
        # retrying will always produce the exact same result, so this is
        # marked CEILING (not a generic "partial") specifically so
        # already_done_institute_years() below treats it as finished
        # rather than something to keep retrying forever.
        note = f"CEILING: retrieved {len(doc_rows)}/{total_results} (Scopus pagination limit, not retryable)"

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
    partial = partial_institute_years()
    if partial:
        print(f"{len(partial)} institution-years have partial/incomplete data from a "
              f"previous run and will be retried cleanly (old rows purged first):")
        for iid, yr in partial:
            print(f"  - {iid} / {yr}")
        print()

    print(f"{len(affiliations)} confirmed institutions, {len(years)} years.\n")

    for institute_id, info in affiliations.items():
        for year in years:
            key = (institute_id, str(year))
            if key in done:
                continue
            if key in partial:
                purge_institute_year(DOCS_CSV, DOC_FIELDS, institute_id, year)
                purge_institute_year(SUMMARY_CSV, SUMMARY_FIELDS, institute_id, year)
            print(f"[{info['name']}] {year} (affilname: {info['affilname']})")
            pull_institute_year(institute_id, info["affilname"], year)

    print(f"\nDone. Per-document data: {DOCS_CSV}")
    print(f"Per-institution-year summary: {SUMMARY_CSV}")
    print(f"Check {FAIL_LOG} for anything that needs attention.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, nargs="+", required=True)
    parser.add_argument("--affiliations", default="data/reference/af_id_candidates_confirmed.csv",
                         help="Path to the confirmed AF-ID CSV")
    args = parser.parse_args()
    main(args.years, args.affiliations)