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

SUMMARY_CSV = Path("data/pipeline/scopus_yearly_summary.csv")
DOCS_CSV = Path("data/pipeline/scopus_raw_documents.csv")
FAIL_LOG = Path("data/pipeline/scopus_failures.log")


def find_failed_institute_years() -> set:
    failed = set()
    if not FAIL_LOG.exists():
        print(f"WARNING: {FAIL_LOG} not found -- nothing to cross-reference.")
        return failed
    with open(FAIL_LOG, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            # status is the LAST field, not a fixed index -- lines have
            # either 3 fields (older format) or 4 (start=N / total=N
            # prefix before the status), so parts[2] was wrong and never
            # matched anything. This was silently a no-op in the first
            # version of this script.
            if len(parts) >= 2 and parts[-1] == "fetch_failed":
                failed.add((parts[0], parts[1]))
    return failed


def purge_and_report(path: Path, key_fields: tuple, to_purge: set) -> int:
    if not path.exists():
        return 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if not fieldnames or not all(k in fieldnames for k in key_fields):
            print(f"  WARNING: {path} doesn't have the expected columns "
                  f"{key_fields} (found: {fieldnames}) -- skipping it. "
                  f"This can happen if it's a Git LFS pointer file rather "
                  f"than the real data (check 'git lfs pull' if so).")
            return 0
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

    with open(SUMMARY_CSV, newline="", encoding="utf-8") as f:
        summary_rows = list(csv.DictReader(f))

    zero_blank = [
        r for r in summary_rows
        if r.get("total_documents", "0") == "0" and not r.get("note", "").strip()
    ]

    # Category 1: confirmed by the fail log as a genuine network/API failure.
    confirmed_failures = {
        (r["institute_id"], r["year"]) for r in zero_blank
        if (r["institute_id"], r["year"]) in failed_keys
    }

    # Category 2: 0 documents, empty note, but NOT in the fail log at all.
    # This is the signature of a query that technically succeeded but used
    # a since-corrected affilname (the query itself returned a real "zero
    # results" answer at the time, for the wrong institution string).
    # Retrying is safe either way: if the name is now correct, it'll pull
    # real data; if the row was always a genuine small/zero-output year,
    # retrying just reconfirms the same result at the cost of one query.
    stale_or_unclear = {
        (r["institute_id"], r["year"]) for r in zero_blank
        if (r["institute_id"], r["year"]) not in failed_keys
    }

    print(f"Category 1 -- confirmed network/API failures ({len(confirmed_failures)}):")
    for iid, yr in sorted(confirmed_failures):
        print(f"  - {iid} / {yr}")

    print(f"\nCategory 2 -- zero/blank but NOT in fail log, likely stale pre-fix "
          f"queries or genuine small output ({len(stale_or_unclear)}):")
    for iid, yr in sorted(stale_or_unclear):
        print(f"  - {iid} / {yr}")

    to_purge = confirmed_failures | stale_or_unclear
    if not to_purge:
        print("\nNothing to clean up.")
        return

    print(f"\nPurging {len(to_purge)} rows total for retry...")
    n1 = purge_and_report(SUMMARY_CSV, ("institute_id", "year"), to_purge)
    n2 = purge_and_report(DOCS_CSV, ("institute_id", "year"), to_purge)
    print(f"Purged {n1} rows from {SUMMARY_CSV}")
    print(f"Purged {n2} rows from {DOCS_CSV}")
    print("\nNext run of scopus_scraper.py will retry these cleanly.")
    print("\nNOTE: IR-O-U-0487 (Tamil Nadu Veterinary University) is in this list,")
    print("but if its affilname in af_id_candidates_confirmed.csv is still the old")
    print("broken one, retrying will just get 0 again -- fix that name first.")


if __name__ == "__main__":
    main()