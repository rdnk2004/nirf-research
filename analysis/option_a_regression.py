"""
Part A: Teaching-Learning Resources (TLR) -> Research Output & Placement Outcomes

Research Question:
Does longitudinal growth in foundational teaching and human-capital resources
(faculty-student ratio, doctoral scholar base) predict meaningful gains in:
  1) Research Productivity (Scopus total documents)
  2) Real Student Outcomes (Placement rate percentage)

Panel Structure:
70 institutions x 5 years (2021-2025) = 350 observations (Balanced Panel).
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor
from linearmodels.panel import PanelOLS, RandomEffects, PooledOLS

from analysis.common import load_panel

OUTPUT_DIR = Path("analysis/results")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def prepare_part_a_data(df: pd.DataFrame) -> pd.DataFrame:
    """Construct analysis variables and 1-year lags for Part A."""
    df = df.copy()

    # Sort strictly by entity and year
    df["year"] = df["year"].astype(int)
    df = df.sort_values(["institute_id", "year"]).reset_index(drop=True)

    # 1. Faculty-to-student ratios
    # Raw ratio in NIRF submissions: total_student_strength / faculty_count (students per faculty member)
    df["students_per_faculty"] = df["faculty_student_ratio"].astype(float)
    # Intuitive ratio: Faculty per 100 students (higher is better/more faculty attention)
    df["faculty_per_100_students"] = (df["faculty_count"] / df["total_student_strength"]) * 100.0

    # 2. Log-transformed variables (handling zeroes safely)
    df["ln_scopus_docs"] = np.log(df["scopus_total_documents"].clip(lower=1))
    df["ln_phd_scholars"] = np.log((df["phd_fulltime_current"].fillna(0) + 1))
    df["ln_total_students"] = np.log(df["total_student_strength"].clip(lower=1))
    df["ln_faculty_count"] = np.log(df["faculty_count"].clip(lower=1))
    df["ln_sponsored_amount"] = np.log((df["sponsored_amount_y1"].fillna(0) + 1))

    df["const"] = 1.0
    df["placement_rate_pct"] = df["placement_rate_pct"].astype(float)
    # Higher studies share of graduating cohort
    df["higher_studies_rate_pct"] = np.where(
        df["total_graduating"] > 0,
        (df["total_higher_studies"] / df["total_graduating"]) * 100.0,
        0.0
    ).clip(0, 100)

    # Cast quartile columns to numeric if available (keep NaNs so sums and counts are strictly accurate)
    for q in ["pct_q1", "pct_q2", "pct_q3", "pct_q4", "quartile_match_rate_pct"]:
        if q in df.columns:
            df[q] = pd.to_numeric(df[q], errors="coerce")

    # 4. Construct 1-year lags (within each institution)
    lag_cols = [
        "faculty_per_100_students",
        "students_per_faculty",
        "ln_phd_scholars",
        "ln_sponsored_amount",
        "ln_total_students"
    ]
    for col in lag_cols:
        df[f"lag_{col}"] = df.groupby("institute_id")[col].shift(1)

    return df


def compute_descriptive_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Compute overall, between, and within summary statistics."""
    vars_to_summarize = [
        ("scopus_total_documents", "Scopus Documents (Raw Count)"),
        ("ln_scopus_docs", "ln(Scopus Documents)"),
        ("placement_rate_pct", "Placement Rate (%)"),
        ("students_per_faculty", "Students per Faculty Member"),
        ("faculty_per_100_students", "Faculty per 100 Students"),
        ("phd_fulltime_current", "Full-time PhD Scholars (Raw)"),
        ("ln_phd_scholars", "ln(Full-time PhD Scholars + 1)"),
        ("total_student_strength", "Total Student Strength"),
        ("ln_total_students", "ln(Total Student Strength)"),
        ("sponsored_amount_y1", "Sponsored Research Funding (INR)"),
        ("ln_sponsored_amount", "ln(Sponsored Research Funding + 1)"),
        ("higher_studies_rate_pct", "Higher Studies Rate (%)"),
        ("pct_q1", "% Q1 Journals"),
        ("pct_q2", "% Q2 Journals"),
        ("pct_q3", "% Q3 Journals"),
        ("pct_q4", "% Q4 Journals"),
        ("quartile_match_rate_pct", "Quartile Match Rate (%)"),
    ]

    records = []
    for var, label in vars_to_summarize:
        s = df[var].dropna()
        overall_mean = s.mean()
        overall_std = s.std()
        val_min = s.min()
        val_p25 = s.quantile(0.25)
        val_median = s.median()
        val_p75 = s.quantile(0.75)
        val_max = s.max()

        # Between-entity variation: std of entity means
        entity_means = df.groupby("institute_id")[var].mean()
        between_std = entity_means.std()

        # Within-entity variation: std of (x_it - entity_mean + overall_mean)
        within_deviations = df[var] - df.groupby("institute_id")[var].transform("mean")
        within_std = within_deviations.std()

        records.append({
            "Variable": label,
            "Code": var,
            "Obs": len(s),
            "Mean": overall_mean,
            "Overall Std": overall_std,
            "Between Std": between_std,
            "Within Std": within_std,
            "Min": val_min,
            "25%": val_p25,
            "Median": val_median,
            "75%": val_p75,
            "Max": val_max,
        })

    table1 = pd.DataFrame(records)
    table1.to_csv(OUTPUT_DIR / "part_a_table1_descriptives.csv", index=False)
    return table1


def compute_correlation_and_vif(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute Pearson correlation matrix and Variance Inflation Factors (VIF)."""
    corr_cols = [
        "ln_scopus_docs",
        "placement_rate_pct",
        "faculty_per_100_students",
        "ln_phd_scholars",
        "ln_total_students",
        "ln_sponsored_amount",
        "higher_studies_rate_pct"
    ]
    corr_matrix = df[corr_cols].corr()
    corr_matrix.to_csv(OUTPUT_DIR / "part_a_table2_correlation_matrix.csv")

    # Centered VIF for Model A1 explanatory variables (with constant)
    vif_features = ["faculty_per_100_students", "ln_phd_scholars", "ln_total_students", "ln_sponsored_amount"]
    vif_data = df[vif_features].dropna()
    vif_data_const = sm.add_constant(vif_data)
    vif_records = []
    for col in vif_features:
        idx = vif_data_const.columns.get_loc(col)
        val = variance_inflation_factor(vif_data_const.values, idx)
        vif_records.append({"Variable": col, "VIF": val})
    vif_df = pd.DataFrame(vif_records)
    vif_df.to_csv(OUTPUT_DIR / "part_a_table2_vif.csv", index=False)

    return corr_matrix, vif_df


def perform_hausman_test(fe_res, re_res) -> tuple[float, float, int]:
    """Perform Hausman specification test comparing Fixed Effects and Random Effects.
    Uses unadjusted (classical) covariance matrices to satisfy Hausman's (1978) asymptotic
    efficiency condition Var(b_fe - b_re) = Var(b_fe) - Var(b_re).
    H0: Random Effects is consistent and efficient.
    H1: Fixed Effects is consistent, RE is inconsistent (endogeneity present).
    """
    try:
        fe_u = fe_res.model.fit(cov_type="unadjusted")
        re_u = re_res.model.fit(cov_type="unadjusted")
        common_params = [p for p in fe_u.params.index if p in re_u.params.index and p != "const"]
        b_fe = fe_u.params[common_params]
        b_re = re_u.params[common_params]
        cov_diff = fe_u.cov.loc[common_params, common_params] - re_u.cov.loc[common_params, common_params]

        diff = b_fe - b_re
        inv_cov_diff = np.linalg.pinv(cov_diff)
        stat = float(diff.T @ inv_cov_diff @ diff)
        df = len(common_params)
        p_val = float(1.0 - stats.chi2.cdf(stat, df))
        return stat, p_val, df
    except Exception:
        return np.nan, np.nan, len(common_params) if "common_params" in locals() else 0


def perform_wooldridge_cre_test(pdata: pd.DataFrame, y_var: str, x_vars: list[str]) -> tuple[float, float, int]:
    """Perform Wooldridge (2010) / Mundlak (1978) Correlated Random Effects robust test.
    Augments the RE model with entity-level time-means and conducts a Wald test that
    their coefficients are jointly zero with cluster-robust standard errors.
    H0: Coefficients on entity time-means are jointly zero (RE is consistent).
    H1: Significant correlation between unobserved heterogeneity and regressors (FE required).
    """
    pdata_sub = pdata.dropna(subset=[y_var] + x_vars).copy()
    mean_cols = []
    for col in x_vars:
        mcol = f"mean_{col}"
        pdata_sub[mcol] = pdata_sub.groupby(level=0)[col].transform("mean")
        mean_cols.append(mcol)

    x_all = ["const"] + x_vars + mean_cols
    re_cre = RandomEffects(pdata_sub[y_var], pdata_sub[x_all]).fit(cov_type="clustered", cluster_entity=True)
    wald = re_cre.wald_test(formula=" = ".join(mean_cols) + " = 0")
    return float(wald.stat), float(wald.pval), len(mean_cols)


def format_panel_results(models_dict: dict) -> pd.DataFrame:
    """Format model results into an academic comparison table."""
    all_vars = []
    for m in models_dict.values():
        all_vars.extend(m.params.index.tolist())
    all_vars = sorted(list(set(all_vars)), key=lambda x: (x == "const", x))

    rows = []
    for v in all_vars:
        row = {"Variable": v}
        for name, m in models_dict.items():
            if v in m.params:
                coef = m.params[v]
                se = m.std_errors[v]
                pval = m.pvalues[v]
                stars = ""
                if pval < 0.01:
                    stars = "***"
                elif pval < 0.05:
                    stars = "**"
                elif pval < 0.10:
                    stars = "*"
                row[name] = f"{coef:.4f}{stars}\n({se:.4f})"
            else:
                row[name] = "-"
        rows.append(row)

    summary_rows = [
        {"Variable": "Observations", **{name: str(m.nobs) for name, m in models_dict.items()}},
        {"Variable": "R-squared", **{name: f"{m.rsquared:.4f}" for name, m in models_dict.items()}},
        {"Variable": "R-squared (Within)", **{name: (f"{m.rsquared_within:.4f}" if hasattr(m, "rsquared_within") else "-") for name, m in models_dict.items()}},
        {"Variable": "Entity Effects", **{name: ("Yes" if getattr(m, "_entity_effects", False) else "No") for name, m in models_dict.items()}},
        {"Variable": "Time/Year Effects", **{name: ("Yes" if getattr(m, "_time_effects", False) else "No") for name, m in models_dict.items()}},
        {"Variable": "Covariance", **{name: "Clustered (Entity)" for name in models_dict.keys()}}
    ]
    res_df = pd.DataFrame(rows + summary_rows)
    return res_df


def run_model_a1_research(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Model A1: Research Output Model
    Target: ln(Scopus Documents)
    Explanatory: Faculty per 100 students, ln(PhD Scholars), controls.
    """
    pdata = df.set_index(["institute_id", "year"])

    y_var = "ln_scopus_docs"
    x_vars = ["faculty_per_100_students", "ln_phd_scholars", "ln_total_students", "ln_sponsored_amount"]
    x_vars_const = ["const"] + x_vars

    # 1. Pooled OLS
    m1 = PooledOLS(pdata[y_var], pdata[x_vars_const]).fit(cov_type="clustered", cluster_entity=True)
    m1._entity_effects = False
    m1._time_effects = False

    # 2. Random Effects
    m2 = RandomEffects(pdata[y_var], pdata[x_vars_const]).fit(cov_type="clustered", cluster_entity=True)
    m2._entity_effects = False
    m2._time_effects = False

    # 3. Entity Fixed Effects (One-way FE)
    m3 = PanelOLS(pdata[y_var], pdata[x_vars], entity_effects=True, time_effects=False).fit(
        cov_type="clustered", cluster_entity=True
    )
    m3._entity_effects = True
    m3._time_effects = False

    # 4. Two-Way Fixed Effects (Entity FE + Year FE)
    m4 = PanelOLS(pdata[y_var], pdata[x_vars], entity_effects=True, time_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )
    m4._entity_effects = True
    m4._time_effects = True

    # 5. Lagged Two-Way Fixed Effects (Inputs at t-1)
    lag_x_vars = ["lag_faculty_per_100_students", "lag_ln_phd_scholars", "lag_ln_total_students", "lag_ln_sponsored_amount"]
    pdata_lag = pdata[[y_var] + lag_x_vars].dropna()
    m5 = PanelOLS(pdata_lag[y_var], pdata_lag[lag_x_vars], entity_effects=True, time_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )
    m5._entity_effects = True
    m5._time_effects = True

    # Specification Tests
    h_stat, h_pval, h_df = perform_hausman_test(m3, m2)
    w_stat, w_pval, w_df = perform_wooldridge_cre_test(pdata, y_var, x_vars)
    diag_text = (
        f"Hausman Test (Unadjusted SEs): Chi2({h_df}) = {h_stat:.3f}, p = {h_pval:.4e} | "
        f"Wooldridge CRE Test (Cluster-Robust): Chi2({w_df}) = {w_stat:.3f}, p = {w_pval:.4e}"
    )

    models = {
        "(1) Pooled OLS": m1,
        "(2) Random Effects": m2,
        "(3) Entity FE": m3,
        "(4) Two-Way FE": m4,
        "(5) Lagged TWFE (t-1)": m5,
    }
    table = format_panel_results(models)
    table.to_csv(OUTPUT_DIR / "part_a_table3_model_a1_research.csv", index=False)
    return table, diag_text


def run_model_a2_placement(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Model A2: Student Placement Outcome Model
    Target: placement_rate_pct (0 to 100)
    Explanatory: Faculty per 100 students, controls.

    NOTE: higher_studies_rate_pct was removed from the RHS here (an
    earlier version used it as a predictor). placement_rate_pct and
    higher_studies_rate_pct are both computed from the SAME
    total_graduating denominator -- a student going to higher studies
    is, near-mechanically, a student not counted as "placed". Using one
    to predict the other risked reporting an arithmetic artifact as a
    causal finding. They are now modeled as two PARALLEL outcomes (see
    run_model_a2b_higher_studies below), both driven by the same
    explanatory variables, rather than one predicting the other.
    """
    pdata = df.set_index(["institute_id", "year"])

    y_var = "placement_rate_pct"
    x_vars = ["faculty_per_100_students", "ln_total_students"]
    x_vars_const = ["const"] + x_vars

    # 1. Pooled OLS
    m1 = PooledOLS(pdata[y_var], pdata[x_vars_const]).fit(cov_type="clustered", cluster_entity=True)
    m1._entity_effects = False
    m1._time_effects = False

    # 2. Random Effects
    m2 = RandomEffects(pdata[y_var], pdata[x_vars_const]).fit(cov_type="clustered", cluster_entity=True)
    m2._entity_effects = False
    m2._time_effects = False

    # 3. Entity Fixed Effects (One-way FE)
    m3 = PanelOLS(pdata[y_var], pdata[x_vars], entity_effects=True, time_effects=False).fit(
        cov_type="clustered", cluster_entity=True
    )
    m3._entity_effects = True
    m3._time_effects = False

    # 4. Two-Way Fixed Effects (Entity FE + Year FE)
    m4 = PanelOLS(pdata[y_var], pdata[x_vars], entity_effects=True, time_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )
    m4._entity_effects = True
    m4._time_effects = True

    # 5. Lagged Two-Way Fixed Effects (Inputs at t-1)
    lag_x_vars = ["lag_faculty_per_100_students", "lag_ln_total_students"]
    pdata_lag = pdata[[y_var] + lag_x_vars].dropna()
    m5 = PanelOLS(pdata_lag[y_var], pdata_lag[lag_x_vars], entity_effects=True, time_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )
    m5._entity_effects = True
    m5._time_effects = True

    # Specification Tests
    h_stat, h_pval, h_df = perform_hausman_test(m3, m2)
    w_stat, w_pval, w_df = perform_wooldridge_cre_test(pdata, y_var, x_vars)
    diag_text = (
        f"Hausman Test (Unadjusted SEs): Chi2({h_df}) = {h_stat:.3f}, p = {h_pval:.4e} | "
        f"Wooldridge CRE Test (Cluster-Robust): Chi2({w_df}) = {w_stat:.3f}, p = {w_pval:.4e}"
    )

    models = {
        "(1) Pooled OLS": m1,
        "(2) Random Effects": m2,
        "(3) Entity FE": m3,
        "(4) Two-Way FE": m4,
        "(5) Lagged TWFE (t-1)": m5,
    }
    table = format_panel_results(models)
    table.to_csv(OUTPUT_DIR / "part_a_table4_model_a2_placement.csv", index=False)
    return table, diag_text


def run_model_a2b_higher_studies(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Model A2b: Higher-Studies Rate Outcome Model (parallel to Model A2)
    Target: higher_studies_rate_pct (0 to 100)
    Explanatory: SAME variables as Model A2 (faculty_per_100_students,
    ln_total_students), so the two post-graduation paths (placed vs.
    higher studies) are modeled as parallel outcomes of the same
    teaching-resource inputs, rather than one predicting the other.
    """
    pdata = df.set_index(["institute_id", "year"])

    y_var = "higher_studies_rate_pct"
    x_vars = ["faculty_per_100_students", "ln_total_students"]
    x_vars_const = ["const"] + x_vars

    m1 = PooledOLS(pdata[y_var], pdata[x_vars_const]).fit(cov_type="clustered", cluster_entity=True)
    m1._entity_effects = False
    m1._time_effects = False

    m2 = RandomEffects(pdata[y_var], pdata[x_vars_const]).fit(cov_type="clustered", cluster_entity=True)
    m2._entity_effects = False
    m2._time_effects = False

    m3 = PanelOLS(pdata[y_var], pdata[x_vars], entity_effects=True, time_effects=False).fit(
        cov_type="clustered", cluster_entity=True
    )
    m3._entity_effects = True
    m3._time_effects = False

    m4 = PanelOLS(pdata[y_var], pdata[x_vars], entity_effects=True, time_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )
    m4._entity_effects = True
    m4._time_effects = True

    lag_x_vars = ["lag_faculty_per_100_students", "lag_ln_total_students"]
    pdata_lag = pdata[[y_var] + lag_x_vars].dropna()
    m5 = PanelOLS(pdata_lag[y_var], pdata_lag[lag_x_vars], entity_effects=True, time_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )
    m5._entity_effects = True
    m5._time_effects = True

    # Specification Tests
    h_stat, h_pval, h_df = perform_hausman_test(m3, m2)
    w_stat, w_pval, w_df = perform_wooldridge_cre_test(pdata, y_var, x_vars)
    diag_text = (
        f"Hausman Test (Unadjusted SEs): Chi2({h_df}) = {h_stat:.3f}, p = {h_pval:.4e} | "
        f"Wooldridge CRE Test (Cluster-Robust): Chi2({w_df}) = {w_stat:.3f}, p = {w_pval:.4e}"
    )

    models = {
        "(1) Pooled OLS": m1,
        "(2) Random Effects": m2,
        "(3) Entity FE": m3,
        "(4) Two-Way FE": m4,
        "(5) Lagged TWFE (t-1)": m5,
    }
    table = format_panel_results(models)
    table.to_csv(OUTPUT_DIR / "part_a_table4b_model_a2b_higher_studies.csv", index=False)
    return table, diag_text


def main():
    print("=" * 80)
    print("PART A: TEACHING-LEARNING RESOURCES -> RESEARCH OUTPUT & PLACEMENT")
    print("=" * 80)

    raw_df = load_panel()
    print(f"Loaded balanced panel: {len(raw_df)} observations across {raw_df['institute_id'].nunique()} institutions.")

    df = prepare_part_a_data(raw_df)

    # 1. Descriptive Statistics
    print("\n--- Generating Table 1: Descriptive Statistics ---")
    t1 = compute_descriptive_stats(df)
    print(t1[["Variable", "Mean", "Overall Std", "Between Std", "Within Std", "Min", "Median", "Max"]].to_string(index=False))

    # 2. Correlation & VIF
    print("\n--- Generating Table 2: Correlation Matrix & VIF ---")
    corr, vif = compute_correlation_and_vif(df)
    print("\nVIF Results:")
    print(vif.to_string(index=False))

    # 3. Model A1: Research Output
    print("\n--- Estimating Model A1: Research Output (ln_scopus_docs) ---")
    t3, h1_text = run_model_a1_research(df)
    print(t3.to_string(index=False))
    print(f"\nDiagnostics: {h1_text}")

    # 4. Model A2: Student Placement
    print("\n--- Estimating Model A2: Student Placement Rate (%) ---")
    t4, h2_text = run_model_a2_placement(df)
    print(t4.to_string(index=False))
    print(f"\nDiagnostics: {h2_text}")

    # 4b. Model A2b: Higher Studies Rate (parallel outcome to A2, not a
    # predictor of it -- see run_model_a2_placement docstring)
    print("\n--- Estimating Model A2b: Higher Studies Rate (%) [parallel outcome to A2] ---")
    t4b, h2b_text = run_model_a2b_higher_studies(df)
    print(t4b.to_string(index=False))
    print(f"\nDiagnostics: {h2b_text}")

    print("\n" + "=" * 80)
    print("Part A estimation complete. Results exported to analysis/results/")
    print("=" * 80)


if __name__ == "__main__":
    main()