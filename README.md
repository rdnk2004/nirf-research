# NIRF Research Data Pipeline & Empirical Analysis

> 📊 **Full Empirical Report & Findings**: See [**`RESEARCH_RESULTS.md`**](file:///d:/nirf-scraper/RESEARCH_RESULTS.md) for the complete paper writeup, regression tables, econometric models, and publication figures.

Data collection, pipeline engineering, and empirical panel analysis evaluating how India's National Institutional Ranking Framework (NIRF) affects university research output, journal quality, and student placement outcomes.

**Panel Scope**: 70 universities × 5 years (2021–2025) = 350 balanced panel observations.

## Two research questions

- **Option A**: Do improvements in teaching-learning resources (faculty-student
  ratio, PhD-student counts) predict growth in research output and placement
  outcomes?
- **Option B**: Is the post-NIRF publication surge concentrated in low-quality
  journals (Q3/Q4), or does it reflect genuine high-impact output?

## Project structure

```
data/
├── final/                          # ← analysis-ready datasets
│   ├── merged_analysis_dataset.csv     # 350 rows × 32 cols — THE dataset
│   ├── journal_quartile_by_institution_year.csv
│   └── EXCLUSIONS.md                   # 70 dropped institutions, documented
├── pipeline/                       # scraper outputs & intermediates
│   ├── nirf_university_raw.csv         # raw NIRF scrape (~145 institutions)
│   ├── nirf_university_raw_clean.csv   # + canonical names
│   ├── nirf_final_70.csv               # filtered to panel
│   ├── scopus_raw_documents.csv        # 637K papers (~143 MB, LFS)
│   ├── scopus_yearly_summary.csv       # per institution-year aggregates
│   ├── scopus_final_70.csv             # filtered to panel
│   └── scopus_failures.log             # retry tracking
└── reference/                      # external lookup/source data
    ├── af_id_candidates_confirmed.csv  # Scopus affiliation mappings
    └── scimagojr-{2021..2025}.csv      # SCImago journal quartile data

src/                                # data pipeline scripts
├── scraper.py                          # NIRF scraper (listings + PDFs)
├── scopus_scraper.py                   # Scopus publication + citation data
├── affliation_lookup.py                # Scopus affiliation candidate finder
├── clean_institution_names.py          # name canonicalization
└── clean_rows.py                       # failure-log cleanup

analysis/                           # statistical analysis (Python)
└── results/                            # generated tables & figures

cache/                              # HTTP/PDF/Scopus response cache (gitignored)
```

## Setup

```bash
pip install -r requirements.txt
```

Scopus API key goes in `.env`:
```
SCOPUS_API_KEY=your_key_here
```

## Key dataset: `data/final/merged_analysis_dataset.csv`

One row per institution-year. 32 columns:

| Group | Columns |
|---|---|
| Identity | `institute_id`, `name_canonical`, `city`, `state`, `year` |
| NIRF scores | `tlr_score`, `rpc_score`, `go_score`, `oi_score`, `pr_score`, `overall_score`, `rank` |
| Teaching resources | `faculty_count`, `total_student_strength`, `faculty_student_ratio` |
| Placement | `total_graduating`, `total_placed`, `total_higher_studies`, `placement_rate_pct` |
| PhD | `phd_fulltime_current`, `phd_parttime_current` |
| Research funding | `sponsored_projects_y1`, `sponsored_amount_y1` |
| Scopus output | `scopus_total_documents`, `scopus_total_citations`, `scopus_avg_citations_per_doc` |
| Journal quality | `matched_journal_docs`, `quartile_match_rate_pct`, `pct_q1`, `pct_q2`, `pct_q3`, `pct_q4` |

## Pipeline scripts

### NIRF scraper (`src/scraper.py`)
```bash
python src/scraper.py --years 2021 2022 2023 2024 2025 --category University
```
Outputs to `data/pipeline/nirf_university_raw.csv`. Cached and resumable —
re-running skips completed rows. **Gotcha**: if you change parsing logic,
delete the output CSV first or resumability will skip re-parsing.

### Name cleanup (`src/clean_institution_names.py`)
```bash
python src/clean_institution_names.py data/pipeline/nirf_university_raw.csv
```
Must be re-run any time the raw CSV changes.

### Scopus affiliation lookup (`src/affliation_lookup.py`)
```bash
python src/affliation_lookup.py --input data/pipeline/nirf_university_raw_clean.csv
```
Generates candidate affiliation names. Manually mark `confirmed=yes` on the
correct row for each institution.

### Scopus scraper (`src/scopus_scraper.py`)
```bash
python src/scopus_scraper.py --years 2021 2022 2023 2024 2025
```
Defaults to `data/reference/af_id_candidates_confirmed.csv` for affiliations.
Cached and resumable. Rate-limited (1s delay). Handles Scopus's 5,000-result
pagination ceiling.

## Known gaps

- **Faculty PhD-qualification rate**: not available from NIRF PDFs (confirmed
  by inspection). Would require NAAC SSR data, which is non-annual —
  structurally incompatible with this panel design. Deliberately excluded.
- **`scopus_avg_citations_per_doc`**: declines mechanically 2021→2025 due to
  citation-accumulation time. Do NOT use for cross-year quality comparison.
  Use journal-quartile percentages (`pct_q1`–`pct_q4`) instead.
- **Quartile match rate**: ~75% of documents match to journal ISSNs. The
  unmatched ~25% are non-journal content (conference proceedings, book
  chapters) — confirmed by sampling, not a data-quality issue.

## Politeness

The NIRF scraper hits a Government of India server. The 1.5-second delay
and retry/backoff logic are intentional — don't reduce `BASE_DELAY_SECONDS`.