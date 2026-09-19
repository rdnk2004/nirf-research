"""
One-time cleanup for a bug that's now fixed in scopus_scraper.py: a
connection failure on an institution-year's FIRST page produced a summary
row with 0 documents, 0 citations, and an EMPTY note -- indistinguishable
from a genuinely completed, zero-output institution. That empty note made
the resumability check treat it as permanently "done."

This script does NOT guess based on "0 documents" alone -- some
institutions may genuinely have very low or zero Scopus-indexed output in
a given year, and blindly purging every zero-count row would throw that
real data away. Instead it cross-references scopus_failures.log, which
DID correctly record every failed fetch attempt even before today's fix,
as ground truth for which rows are actual failures.

What it does:
  1. Reads scopus_failures.log for every (institute_id, year) that had a
     "fetch_failed" entry.
  2. For each of those, if the corresponding summary row shows 0 total
     documents AND an empty note, it's purged from BOTH
     scopus_yearly_summary.csv and scopus_raw_documents.csv (using the
     same purge logic as the main script) so the next run retries it
     cleanly instead of skipping it forever.
  3. Everything else is left untouched -- including any 0-document row
     that ISN'T in the fail log, since that's more likely a real
     confirmed-empty result than a silent failure.

Usage:
    python3 clean_failed_rows.py
"""

import csv
from pathlib import Path

SUMMARY_CSV = Path("output/scopus_yearly_summary.csv")
DOCS_CSV = Path("output/scopus_raw_documents.csv")
FAIL_LOG = Path("output/scopus_failures.log")


def find_failed_institute_years() -> set:
    failed = set()
    if not FAIL_LOG.exists():
        print(f"WARNING: {FAIL_LOG} not found -- nothing to cross-reference.")
        return failed
    with open(FAIL_LOG, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 3 and parts[2] == "fetch_failed":
                failed.add((parts[0], parts[1]))
    return failed


def purge_and_report(path: Path, key_fields: tuple, to_purge: set) -> int:
    if not path.exists():
        return 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    kept = []
    purged = 0
    for r in rows:
        key = (r[key_fields[0]], r[key_fields[1]])
        if key in to_purge:
            purged += 1
        else:
            kept.append(r)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)

    return purged


def main():
    failed_keys = find_failed_institute_years()
    print(f"Found {len(failed_keys)} (institute_id, year) pairs with a logged fetch failure.\n")

    if not SUMMARY_CSV.exists():
        print(f"ERROR: {SUMMARY_CSV} not found.")
        return

    # Only purge summary rows that BOTH appear in the fail log AND show
    # 0 documents with an empty note -- this is the exact signature of
    # the bug, not a blanket "delete anything with 0 documents" sweep.
    with open(SUMMARY_CSV, newline="", encoding="utf-8") as f:
        summary_rows = list(csv.DictReader(f))

    confirmed_bad = set()
    for r in summary_rows:
        key = (r["institute_id"], r["year"])
        if (key in failed_keys
                and r.get("total_documents", "0") == "0"
                and not r.get("note", "").strip()):
            confirmed_bad.add(key)

    print(f"Of those, {len(confirmed_bad)} match the bug's exact signature "
          f"(0 documents, empty note) and will be purged for retry:")
    for iid, yr in sorted(confirmed_bad):
        print(f"  - {iid} / {yr}")

    if not confirmed_bad:
        print("\nNothing to clean up.")
        return

    n1 = purge_and_report(SUMMARY_CSV, ("institute_id", "year"), confirmed_bad)
    n2 = purge_and_report(DOCS_CSV, ("institute_id", "year"), confirmed_bad)
    print(f"\nPurged {n1} rows from {SUMMARY_CSV}")
    print(f"Purged {n2} rows from {DOCS_CSV}")
    print("\nNext run of scopus_scraper.py will retry these cleanly.")


if __name__ == "__main__":
    main()