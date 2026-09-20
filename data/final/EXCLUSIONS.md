# Final Panel: Exclusion Documentation

**Final panel: 70 institutions x 5 years (2021-2025) = 350 institution-year observations.**

Started from 140 confirmed institutions (top-100 NIRF University category ranking
appearing at least once across 2021-2025, with a verified Scopus affiliation match).
70 were dropped, for two distinct reasons:

## 1. Dropped for incomplete NIRF ranking coverage (63 institutions)

These institutions were not ranked in the NIRF top-100 for all five years
2021-2025 (they moved in and out of the top 100 across years), so their
Scopus publication data exists but their NIRF teaching-resource data
(faculty count, student strength) does not, for the missing years. Rather
than analyze an unbalanced panel, only institutions with full 5/5 year
NIRF coverage were retained, for a clean, directly comparable panel.

## 2. Dropped for unresolved Scopus affiliation-matching (7 institutions)

After repeated attempts to identify the correct Scopus affiliation name
(including live verification queries), these 7 institutions still could
not be reliably matched, and their true publication output for at least
one year could not be confirmed:

| Institution | institute_id | Issue |
|---|---|---|
| Kalinga Institute of Industrial Technology | IR-O-U-0356 | 2021 unresolved |
| Professor Jayashankar Telangana State Agricultural University | IR-O-U-0784 | 2021-22 unresolved |
| Rajiv Gandhi University | IR-O-U-0047 | 2021-23 unresolved |
| Gujarat University | IR-O-U-0136 | 2022 unresolved |
| Datta Meghe Institute of Higher Education and Research | IR-O-U-0295 | 2021 unresolved |
| Krishna Institute of Medical Sciences | IR-O-C-23033 | 2021-22 unresolved |
| Krishna Institute of Medical Sciences Deemed University, Karad | IR-O-U-0311 | 2021-22 unresolved |

Note: these last two both mapped to the same Scopus affiliation name
("Krishna Vishwa Vidyapeeth Deemed To Be University") during
investigation -- whether these are genuinely two distinct NIRF-ranked
entities or a single institution counted twice was not resolved, which
was an additional reason to exclude both rather than risk double-counting.

## Data sources per institution-year

- **NIRF data**: scraped from nirfindia.org's public "Data Submitted by
  Institution" PDFs (faculty count, student strength, PhD counts,
  sponsored research) plus listing-page composite scores (TLR, RPC, GO,
  OI, PR, overall score, rank).
- **Scopus data**: pulled via the Scopus Search API (AFFIL query per
  institution per year), aggregating total documents, total citations,
  and average citations per document.
