"""
Canonicalizes institution names in the NIRF CSV: same institute_id can have
different name strings across years (punctuation, "and" vs "&", trailing
city name, etc.) due to NIRF's own submission inconsistency, not a scraper
bug. This does NOT touch institute_id (already consistent) -- it only adds
a clean display-name column for labeling tables/charts.

Usage:
    python3 clean_institution_names.py data/pipeline/nirf_university_raw.csv
"""
import csv
import sys
from collections import Counter

def canonical_name(names: list[str]) -> str:
    """Pick the longest name as canonical (usually the most complete/specific one,
    e.g. 'Indian Institute of Science, Bengaluru' over 'Indian Institute of Science')."""
    return max(names, key=len)

def main(path: str):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    id_to_names = {}
    for r in rows:
        id_to_names.setdefault(r["institute_id"], []).append(r["name"])

    canon_map = {iid: canonical_name(names) for iid, names in id_to_names.items()}

    changed = 0
    for r in rows:
        canon = canon_map[r["institute_id"]]
        if r["name"] != canon:
            changed += 1
        r["name_canonical"] = canon

    if "name_canonical" not in fieldnames:
        fieldnames.insert(fieldnames.index("name") + 1, "name_canonical")

    out_path = path.replace(".csv", "_clean.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"{changed} rows had a non-canonical name string.")
    print(f"Added 'name_canonical' column. Written to: {out_path}")
    print()
    print("Institutions with more than one name variant seen:")
    for iid, names in id_to_names.items():
        uniq = set(names)
        if len(uniq) > 1:
            print(f"  {iid}: canonical = '{canon_map[iid]}'  |  variants seen: {uniq}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/pipeline/nirf_university_raw.csv")