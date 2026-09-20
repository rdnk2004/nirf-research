"""
Option B: Journal-Quality Channel Analysis

Research question: Is the post-NIRF publication surge concentrated in
low-quality (Q3/Q4) journals, or does it reflect genuine high-impact
research (Q1/Q2)?

Panel: 70 institutions × 5 years (2021-2025)

Key variables:
  - pct_q1, pct_q2, pct_q3, pct_q4 (journal quality distribution)
  - scopus_total_documents (publication volume)
  - quartile_match_rate_pct (data coverage indicator)

Note on citation-age confound:
  scopus_avg_citations_per_doc declines mechanically 2021→2025
  (older papers accumulate more citations). Do NOT use for cross-year
  quality comparison. Journal quartiles (fixed at publication time)
  are the correct metric — confirmed flat/noisy across years.
"""

# TODO: Implement quality-channel analysis
# - Trend analysis: are pct_q3 + pct_q4 rising over time?
# - Does volume growth (scopus_total_documents) predict quality shift?
# - Institution-level heterogeneity: do lower-ranked institutions
#   show more quality degradation?
# - Consider: interaction between rank tier and year for quartile shares
