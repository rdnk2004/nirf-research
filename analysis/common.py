"""
Shared data loading and preparation for Option A and Option B analyses.

Loads the merged panel dataset and provides common transformations:
- Panel setup (institution × year)
- Descriptive statistics
- Variable construction (growth rates, lags, etc.)
"""

import pandas as pd
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data/final/merged_analysis_dataset.csv"


def load_panel() -> pd.DataFrame:
    """Load the merged analysis dataset as a pandas DataFrame.

    Returns a 350-row panel (70 institutions × 5 years, 2021-2025)
    with all NIRF, Scopus, and journal-quartile columns.
    """
    df = pd.read_csv(DATA_PATH)

    # Ensure correct types
    df["year"] = df["year"].astype(int)
    df["rank"] = pd.to_numeric(df["rank"], errors="coerce")

    # Sort for panel structure
    df = df.sort_values(["institute_id", "year"]).reset_index(drop=True)

    return df


def descriptive_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Generate descriptive statistics for all numeric columns."""
    numeric_cols = df.select_dtypes(include="number").columns
    return df[numeric_cols].describe().T


def add_growth_rates(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Add year-over-year growth rate columns for specified variables.

    Growth rate = (x_t - x_{t-1}) / x_{t-1} × 100
    First year (2021) will be NaN for each institution.
    """
    df = df.copy()
    for col in cols:
        df[f"{col}_growth"] = (
            df.groupby("institute_id")[col]
            .pct_change() * 100
        )
    return df


if __name__ == "__main__":
    df = load_panel()
    print(f"Panel loaded: {len(df)} rows, {len(df.columns)} columns")
    print(f"Institutions: {df['institute_id'].nunique()}")
    print(f"Years: {sorted(df['year'].unique())}")
    print(f"\nColumn groups:")
    print(f"  NIRF scores: tlr_score ... overall_score, rank")
    print(f"  Teaching: faculty_count, total_student_strength, faculty_student_ratio")
    print(f"  Placement: placement_rate_pct")
    print(f"  PhD: phd_fulltime_current, phd_parttime_current")
    print(f"  Scopus: scopus_total_documents, scopus_total_citations, scopus_avg_citations_per_doc")
    print(f"  Quality: pct_q1, pct_q2, pct_q3, pct_q4 (quartile_match_rate_pct)")
    print(f"\n{descriptive_stats(df).to_string()}")
