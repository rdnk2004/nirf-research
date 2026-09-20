"""
Option A: Teaching-Learning Resources → Research Output & Placement

Research question: Does growth in teaching-learning resources
(faculty-student ratio, PhD-student counts) predict growth in
research output and real student outcomes (placement rate)?

Panel: 70 institutions × 5 years (2021-2025)

Key variables:
  Independent (TLR proxies):
    - faculty_student_ratio
    - phd_fulltime_current + phd_parttime_current
  Dependent:
    - scopus_total_documents (research output)
    - placement_rate_pct (student outcome)
  Controls:
    - total_student_strength (institution size)
    - sponsored_amount_y1 (research funding)
"""

# TODO: Implement panel regression
# - Fixed-effects model (institution FE to control for time-invariant characteristics)
# - Consider year FE as well
# - Check for multicollinearity (VIF)
# - Hausman test: fixed vs. random effects
# - Robust standard errors (clustered by institution)
