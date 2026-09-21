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

    # VIF for Model A1 explanatory variables
    vif_features = ["faculty_per_100_students", "ln_phd_scholars", "ln_total_students", "ln_sponsored_amount"]
    vif_data = df[vif_features].dropna()
    vif_records = []
    for i, col in enumerate(vif_features):
        val = variance_inflation_factor(vif_data.values, i)
        vif_records.append({"Variable": col, "VIF": val})
    vif_df = pd.DataFrame(vif_records)
    vif_df.to_csv(OUTPUT_DIR / "part_a_table2_vif.csv", index=False)

    return corr_matrix, vif_df


def perform_hausman_test(fe_res, re_res) -> tuple[float, float, int]:
    """Perform Hausman specification test comparing Fixed Effects and Random Effects.
    H0: Random Effects is consistent and efficient.
    H1: Fixed Effects is consistent, RE is inconsistent (endogeneity present).
    """
    common_params = [p for p in fe_res.params.index if p in re_res.params.index and p != "const"]
    b_fe = fe_res.params[common_params]
    b_re = re_res.params[common_params]
    cov_diff = fe_res.cov.loc[common_params, common_params] - re_res.cov.loc[common_params, common_params]

    diff = b_fe - b_re
    try:
        inv_cov_diff = np.linalg.pinv(cov_diff)
        stat = float(diff.T @ inv_cov_diff @ diff)
        stat = abs(stat)
        df = len(common_params)
        p_val = float(1.0 - stats.chi2.cdf(stat, df))
        return stat, p_val, df
    except Exception:
        return np.nan, np.nan, len(common_params)


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

    # Hausman Test
    h_stat, h_pval, h_df = perform_hausman_test(m3, m2)
    hausman_text = f"Hausman Test (Model 3 FE vs. Model 2 RE): Chi2({h_df}) = {h_stat:.3f}, p-value = {h_pval:.4e}"

    models = {
        "(1) Pooled OLS": m1,
        "(2) Random Effects": m2,
        "(3) Entity FE": m3,
        "(4) Two-Way FE": m4,
        "(5) Lagged TWFE (t-1)": m5,
    }
    table = format_panel_results(models)
    table.to_csv(OUTPUT_DIR / "part_a_table3_model_a1_research.csv", index=False)
    return table, hausman_text


def run_model_a2_placement(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Model A2: Student Placement Outcome Model
    Target: placement_rate_pct (0 to 100)
    Explanatory: Faculty per 100 students, Higher studies rate, controls.
    """
    pdata = df.set_index(["institute_id", "year"])

    y_var = "placement_rate_pct"
    x_vars = ["faculty_per_100_students", "higher_studies_rate_pct", "ln_total_students"]
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
    lag_x_vars = ["lag_faculty_per_100_students", "higher_studies_rate_pct", "lag_ln_total_students"]
    pdata_lag = pdata[[y_var] + lag_x_vars].dropna()
    m5 = PanelOLS(pdata_lag[y_var], pdata_lag[lag_x_vars], entity_effects=True, time_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )
    m5._entity_effects = True
    m5._time_effects = True

    # Hausman Test
    h_stat, h_pval, h_df = perform_hausman_test(m3, m2)
    hausman_text = f"Hausman Test (Model 3 FE vs. Model 2 RE): Chi2({h_df}) = {h_stat:.3f}, p-value = {h_pval:.4e}"

    models = {
        "(1) Pooled OLS": m1,
        "(2) Random Effects": m2,
        "(3) Entity FE": m3,
        "(4) Two-Way FE": m4,
        "(5) Lagged TWFE (t-1)": m5,
    }
    table = format_panel_results(models)
    table.to_csv(OUTPUT_DIR / "part_a_table4_model_a2_placement.csv", index=False)
    return table, hausman_text


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

    print("\n" + "=" * 80)
    print("Part A estimation complete. Results exported to analysis/results/")
    print("=" * 80)


if __name__ == "__main__":
    main()
