# NIRF University Scraper

Pulls two layers of NIRF data for the University category, per year:

1. **Listing-page composite scores** — TLR, RPC, GO, OI, PR, overall score, rank
2. **Individual "Data Submitted by Institution" PDF** — real faculty count,
   PhD student counts (enrolled + graduated), sponsored research
   projects/funding — the raw numbers behind the composite scores

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
python nirf_scraper.py --years 2019 2020 2021 2022 2023 2024 2025 --category University
```

Results land in `output/nirf_university_raw.csv` (one row per institution
per year). Anything that failed to parse cleanly is logged to
`output/parse_failures.log` — check that file after each run.

Re-running the same command is safe and cheap: every fetched page and PDF
is cached under `cache/`, and rows already written to the CSV are skipped.
If the script gets rate-limited or you kill it partway through, just run
the same command again.

## What's verified vs. what isn't

**Verified against real NIRF data before this was handed to you:**
- The PDF-parsing regexes (faculty count, PhD enrolled/graduated,
  sponsored research) were tested against actual extracted text from
  two different institutions (IIT Madras 2024, IIT Delhi 2024) and
  matched correctly on both.
- The raw-data PDF template is confirmed stable across at least three
  years (2020, 2022, 2024) and across institutions.
- The URL-pattern change (pre-2020 `nirfindia.org/<year>/...` vs.
  2020+ `nirfindia.org/Rankings/<year>/...`) is handled — the script
  tries both.

**NOT independently tested (couldn't reach nirfindia.org from the
environment this was built in — no live network access there):**
- The **listing-page HTML parser** (`parse_listing_html`). It's written
  defensively against the page structure I inspected, but I could only
  check that structure via a text-rendered version of the page, not the
  raw HTML. **Run it on one year first and manually spot-check 3-4 rows
  against the actual NIRF website before trusting the full run.** If
  names/scores come out wrong or missing, the fix is almost certainly in
  `parse_listing_html` — send me a saved copy of the actual HTML
  (`cache/html/*.html` after a run) and I'll correct the selectors.
- Whether the financial (capital/operational expenditure) figures are
  worth extracting too — the parser currently skips these since your
  design doesn't need them, but they're in the raw text if you want them
  later (see `faculty_section_raw`-style extension).

## Known gap: faculty PhD-qualification breakdown

The "Faculty Details" section only reliably yielded `Number of faculty
members entered: <N>` in the samples this was built against — a bare
headcount, not a PhD-qualified vs. non-PhD split. Whether that split
exists further down in the same PDF section couldn't be confirmed with
certainty (the sample might have been truncated by the tool used to
inspect it, not by the source PDF itself).

**Check this yourself in your first run**: every row's
`faculty_section_raw` column contains the full raw text from "Faculty
Details" onward, regardless of whether the structured fields matched
anything. Open that column for a few rows. If a PhD/qualification
breakdown is sitting in there, paste me a sample and I'll extend the
regex to pull it into its own column properly.

## CSV columns

| Column | Meaning |
|---|---|
| `year`, `institute_id`, `name`, `city`, `state` | Identity |
| `tlr_score` ... `pr_score`, `overall_score`, `rank` | NIRF composite scores (0-100) |
| `faculty_count` | Raw faculty headcount as submitted |
| `phd_fulltime_current`, `phd_parttime_current` | PhD students currently enrolled |
| `phd_graduated_*_y1/y2/y3` | PhD graduates, most recent 3 years |
| `sponsored_projects_y1/y2/y3` | Count of funded research projects |
| `sponsored_funding_agencies_y1/y2/y3` | Distinct funding agencies |
| `sponsored_amount_y1/y2/y3` | Total funding received (INR) |
| `parse_status` | `ok`, or a note on what went wrong for that row |
| `faculty_section_raw` | Full unparsed text — your safety net |

## A note on politeness

This hits a Government of India server. The 1.5-second delay between
requests and the retry/backoff logic are there on purpose — don't reduce
`BASE_DELAY_SECONDS` to speed things up. A full run across ~20
universities × ~8 years is roughly 300-400 requests either way; let it run
in the background rather than rushing it.