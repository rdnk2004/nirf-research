"""
Part B: Journal-Quality Channel & Gaming Analysis (SCImago Quartiles Q1-Q4)

Research Question:
Did the post-NIRF surge in publication volume dilute research quality by
channeling papers into lower-tier journals (Q3/Q4), or did universities
successfully scale up high-impact research (Q1/Q2)?

Dataset:
70 institutions x 5 years (2021-2025) = 350 observations.
Matched against SCImago per-year journal quartile snapshots (zero citation-age artifact).
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from linearmodels.panel import PanelOLS, RandomEffects, PooledOLS

from analysis.common import load_panel
from analysis.option_a_regression import perform_hausman_test, perform_wooldridge_cre_test, format_panel_results

FIGURES_DIR = Path("analysis/results/figures")
FIGURES_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR = Path("analysis/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Aesthetic styling
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.sans-serif"] = "DejaVu Sans"
plt.rcParams["axes.edgecolor"] = "#333333"
plt.rcParams["axes.linewidth"] = 0.8


def prepare_part_b_data(df: pd.DataFrame) -> pd.DataFrame:
    """Construct Part B analysis variables, composites, tiers, and lags."""
    df = df.copy()

    df["year"] = df["year"].astype(int)
    df = df.sort_values(["institute_id", "year"]).reset_index(drop=True)

    # 1. Clean quartile columns (preserve NaNs for rows with 0 matched journal docs e.g. MGU 2024)
    q_cols = ["pct_q1", "pct_q2", "pct_q3", "pct_q4"]
    for col in q_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 2. Composite quality metrics (NaN preserved if quartiles missing)
    df["pct_q1_q2"] = np.where(df["pct_q1"].isna(), np.nan, (df["pct_q1"] + df["pct_q2"]).clip(0, 100))
    df["pct_q3_q4"] = np.where(df["pct_q3"].isna(), np.nan, (df["pct_q3"] + df["pct_q4"]).clip(0, 100))
    df["q1_to_q4_ratio"] = np.where(
        df["pct_q4"].isna() | (df["pct_q4"] == 0),
        np.nan,
        df["pct_q1"] / df["pct_q4"]
    )

    # 3. Log transformations of inputs & outputs
    df["ln_scopus_docs"] = np.log(df["scopus_total_documents"].clip(lower=1))
    df["ln_phd_scholars"] = np.log((df["phd_fulltime_current"].fillna(0) + 1))
    df["ln_total_students"] = np.log(df["total_student_strength"].clip(lower=1))
    df["ln_sponsored_amount"] = np.log((df["sponsored_amount_y1"].fillna(0) + 1))
    df["faculty_per_100_students"] = (df["faculty_count"] / df["total_student_strength"]) * 100.0

    # 4. Rank tier assignment: baseline (2021) rank to avoid look-ahead bias
    rank_2021 = df[df["year"] == 2021].set_index("institute_id")["rank"]
    tier_map = {iid: ("Tier 1 (Rank 1-35)" if r <= 35 else "Tier 2 (Rank 36-70)") for iid, r in rank_2021.items()}
    df["tier"] = df["institute_id"].map(tier_map)

    # 5. Constant for OLS / RE
    df["const"] = 1.0

    # 6. Lags within institution (including faculty_per_100_students)
    lag_vars = ["ln_scopus_docs", "pct_q1", "pct_q1_q2", "ln_phd_scholars", "ln_sponsored_amount", "faculty_per_100_students"]
    for v in lag_vars:
        df[f"lag_{v}"] = df.groupby("institute_id")[v].shift(1)

    return df


def generate_table_b1_trends(df: pd.DataFrame) -> pd.DataFrame:
    """Table B1: 5-Year Evolution of Research Volume and Journal Quartiles by Tier."""
    rows = []
    years = sorted(df["year"].unique())

    for yr in years:
        sub_yr = df[df["year"] == yr]

        # Full sample
        rows.append({
            "Year": yr,
            "Sample": "Full Panel (N=70)",
            "Mean Scopus Volume": sub_yr["scopus_total_documents"].mean(),
            "Median Scopus Volume": sub_yr["scopus_total_documents"].median(),
            "Match Rate (%)": sub_yr["quartile_match_rate_pct"].mean(),
            "Mean % Q1": sub_yr["pct_q1"].mean(),
            "Mean % Q2": sub_yr["pct_q2"].mean(),
            "Mean % Q3": sub_yr["pct_q3"].mean(),
            "Mean % Q4": sub_yr["pct_q4"].mean(),
            "Mean % Q1+Q2": sub_yr["pct_q1_q2"].mean(),
            "Mean % Q3+Q4": sub_yr["pct_q3_q4"].mean(),
        })

        # Tier 1
        t1 = sub_yr[sub_yr["tier"] == "Tier 1 (Rank 1-35)"]
        rows.append({
            "Year": yr,
            "Sample": "Tier 1: Rank 1-35 (N=34)",
            "Mean Scopus Volume": t1["scopus_total_documents"].mean(),
            "Median Scopus Volume": t1["scopus_total_documents"].median(),
            "Match Rate (%)": t1["quartile_match_rate_pct"].mean(),
            "Mean % Q1": t1["pct_q1"].mean(),
            "Mean % Q2": t1["pct_q2"].mean(),
            "Mean % Q3": t1["pct_q3"].mean(),
            "Mean % Q4": t1["pct_q4"].mean(),
            "Mean % Q1+Q2": t1["pct_q1_q2"].mean(),
            "Mean % Q3+Q4": t1["pct_q3_q4"].mean(),
        })

        # Tier 2
        t2 = sub_yr[sub_yr["tier"] == "Tier 2 (Rank 36-70)"]
        rows.append({
            "Year": yr,
            "Sample": "Tier 2: Rank 36-70 (N=36)",
            "Mean Scopus Volume": t2["scopus_total_documents"].mean(),
            "Median Scopus Volume": t2["scopus_total_documents"].median(),
            "Match Rate (%)": t2["quartile_match_rate_pct"].mean(),
            "Mean % Q1": t2["pct_q1"].mean(),
            "Mean % Q2": t2["pct_q2"].mean(),
            "Mean % Q3": t2["pct_q3"].mean(),
            "Mean % Q4": t2["pct_q4"].mean(),
            "Mean % Q1+Q2": t2["pct_q1_q2"].mean(),
            "Mean % Q3+Q4": t2["pct_q3_q4"].mean(),
        })

    table_b1 = pd.DataFrame(rows)
    table_b1.to_csv(RESULTS_DIR / "part_b_table1_quartile_trends.csv", index=False)
    return table_b1


def run_model_b1_q1_regressions(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Model B1: Does Publication Volume Dilute Q1 Journal Share?
    Target: pct_q1
    Explanatory: ln(Scopus Volume), ln(PhD Scholars), controls.
    """
    pdata = df.set_index(["institute_id", "year"])

    y_var = "pct_q1"
    x_vars = ["ln_scopus_docs", "ln_phd_scholars", "faculty_per_100_students", "ln_sponsored_amount"]
    x_vars_const = ["const"] + x_vars

    # Drop NaNs for quartile data (e.g. MGU 2024 with 0 matched docs, N=349)
    pdata_clean = pdata.dropna(subset=[y_var] + x_vars)

    m1 = PooledOLS(pdata_clean[y_var], pdata_clean[x_vars_const]).fit(cov_type="clustered", cluster_entity=True)
    m1._entity_effects = False
    m1._time_effects = False

    m2 = RandomEffects(pdata_clean[y_var], pdata_clean[x_vars_const]).fit(cov_type="clustered", cluster_entity=True)
    m2._entity_effects = False
    m2._time_effects = False

    m3 = PanelOLS(pdata_clean[y_var], pdata_clean[x_vars], entity_effects=True, time_effects=False).fit(
        cov_type="clustered", cluster_entity=True
    )
    m3._entity_effects = True
    m3._time_effects = False

    m4 = PanelOLS(pdata_clean[y_var], pdata_clean[x_vars], entity_effects=True, time_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )
    m4._entity_effects = True
    m4._time_effects = True

    # 1-year lagged model (pure lag: all regressors at t-1)
    lag_x_vars = ["lag_ln_scopus_docs", "lag_ln_phd_scholars", "lag_faculty_per_100_students", "lag_ln_sponsored_amount"]
    pdata_lag = pdata[[y_var] + lag_x_vars].dropna()
    m5 = PanelOLS(pdata_lag[y_var], pdata_lag[lag_x_vars], entity_effects=True, time_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )
    m5._entity_effects = True
    m5._time_effects = True

    h_stat, h_pval, h_df = perform_hausman_test(m3, m2)
    w_stat, w_pval, w_df = perform_wooldridge_cre_test(pdata_clean, y_var, x_vars)
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
    table.to_csv(RESULTS_DIR / "part_b_table2_model_b1_q1.csv", index=False)
    return table, diag_text


def run_model_b1b_high_vs_low_regressions(df: pd.DataFrame) -> pd.DataFrame:
    """Model B1b: Two-Way Fixed Effects across multiple quartile thresholds.
    Targets:
      - pct_q1 (Elite journals)
      - pct_q1_q2 (High-tier journals combined)
      - pct_q4 (Marginal journals)
      - pct_q3_q4 (Lower-tier journals combined)
    """
    pdata = df.set_index(["institute_id", "year"])
    x_vars = ["ln_scopus_docs", "ln_phd_scholars", "faculty_per_100_students", "ln_sponsored_amount"]

    targets = {
        "pct_q1": "Target: % Q1 (Elite)",
        "pct_q1_q2": "Target: % Q1 + Q2 (High Tier)",
        "pct_q4": "Target: % Q4 (Bottom Tier)",
        "pct_q3_q4": "Target: % Q3 + Q4 (Lower Half)",
    }

    models = {}
    for target_col, label in targets.items():
        sub = pdata.dropna(subset=[target_col] + x_vars)
        m = PanelOLS(sub[target_col], sub[x_vars], entity_effects=True, time_effects=True).fit(
            cov_type="clustered", cluster_entity=True
        )
        m._entity_effects = True
        m._time_effects = True
        models[label] = m

    table = format_panel_results(models)
    table.to_csv(RESULTS_DIR / "part_b_table3_model_b1b_high_vs_low.csv", index=False)
    return table


def run_model_b2_subgroup_quality(df: pd.DataFrame) -> pd.DataFrame:
    """Model B2: Subgroup Quality Dynamics (Tier 1 vs. Tier 2 Two-Way Fixed Effects)."""
    pdata = df.set_index(["institute_id", "year"])
    x_vars = ["ln_scopus_docs", "ln_phd_scholars", "faculty_per_100_students", "ln_sponsored_amount"]

    pdata_t1 = pdata[pdata["tier"] == "Tier 1 (Rank 1-35)"].dropna(subset=["pct_q1", "pct_q4"] + x_vars)
    pdata_t2 = pdata[pdata["tier"] == "Tier 2 (Rank 36-70)"].dropna(subset=["pct_q1", "pct_q4"] + x_vars)

    m_t1_q1 = PanelOLS(pdata_t1["pct_q1"], pdata_t1[x_vars], entity_effects=True, time_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )
    m_t1_q1._entity_effects = True
    m_t1_q1._time_effects = True

    m_t2_q1 = PanelOLS(pdata_t2["pct_q1"], pdata_t2[x_vars], entity_effects=True, time_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )
    m_t2_q1._entity_effects = True
    m_t2_q1._time_effects = True

    m_t1_q4 = PanelOLS(pdata_t1["pct_q4"], pdata_t1[x_vars], entity_effects=True, time_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )
    m_t1_q4._entity_effects = True
    m_t1_q4._time_effects = True

    m_t2_q4 = PanelOLS(pdata_t2["pct_q4"], pdata_t2[x_vars], entity_effects=True, time_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )
    m_t2_q4._entity_effects = True
    m_t2_q4._time_effects = True

    models = {
        "% Q1: Tier 1 (1-35)": m_t1_q1,
        "% Q1: Tier 2 (36-70)": m_t2_q1,
        "% Q4: Tier 1 (1-35)": m_t1_q4,
        "% Q4: Tier 2 (36-70)": m_t2_q4,
    }

    table = format_panel_results(models)
    table.to_csv(RESULTS_DIR / "part_b_table4_subgroup_quality.csv", index=False)
    return table


def plot_fig5_quartile_stacked_distribution(df: pd.DataFrame):
    """Figure 5: 5-Year Evolution of Journal Quartiles: Tier 1 vs. Tier 2."""
    yearly_tier = df.groupby(["year", "tier"])[["pct_q1", "pct_q2", "pct_q3", "pct_q4"]].mean().reset_index()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), dpi=300, sharey=True)

    quartile_colors = ["#2b5c8f", "#5c92c9", "#e29d52", "#d95f02"]
    q_labels = ["Q1 (Top 25%)", "Q2 (25–50%)", "Q3 (50–75%)", "Q4 (Bottom 25%)"]

    # Tier 1
    t1_data = yearly_tier[yearly_tier["tier"] == "Tier 1 (Rank 1-35)"].set_index("year")[["pct_q1", "pct_q2", "pct_q3", "pct_q4"]]
    t1_data.plot(
        kind="bar",
        stacked=True,
        color=quartile_colors,
        ax=ax1,
        width=0.6,
        edgecolor="white"
    )
    ax1.set_title("Panel A: Tier 1 Universities (Rank 1–35)", fontsize=12, weight="bold", pad=10)
    ax1.set_xlabel("Year", fontsize=11)
    ax1.set_ylabel("Share of Matched Journal Publications (%)", fontsize=11)
    ax1.set_ylim(0, 105)
    ax1.set_xticklabels(t1_data.index, rotation=0)
    ax1.legend().remove()

    # Tier 2
    t2_data = yearly_tier[yearly_tier["tier"] == "Tier 2 (Rank 36-70)"].set_index("year")[["pct_q1", "pct_q2", "pct_q3", "pct_q4"]]
    t2_data.plot(
        kind="bar",
        stacked=True,
        color=quartile_colors,
        ax=ax2,
        width=0.6,
        edgecolor="white"
    )
    ax2.set_title("Panel B: Tier 2 Universities (Rank 36–70)", fontsize=12, weight="bold", pad=10)
    ax2.set_xlabel("Year", fontsize=11)
    ax2.set_xticklabels(t2_data.index, rotation=0)
    ax2.legend(q_labels, title="Journal Tier", loc="upper right", frameon=True, facecolor="white")

    fig.suptitle("Figure 5: Longitudinal Journal Quartile Distribution by Rank Tier (2021–2025)", fontsize=13, weight="bold", y=1.02)
    plt.tight_layout()

    out_path = FIGURES_DIR / "fig5_quartile_distribution_by_tier.png"
    plt.savefig(out_path)
    plt.close()
    print(f"Saved: {out_path}")


def plot_fig6_volume_vs_quality(df: pd.DataFrame):
    """Figure 6: Testing the Dilution Hypothesis: Publication Volume vs. % Q1 Share."""
    fig, ax = plt.subplots(figsize=(9.5, 6), dpi=300)

    palette = {"Tier 1 (Rank 1-35)": "#1f77b4", "Tier 2 (Rank 36-70)": "#ff7f0e"}

    sns.scatterplot(
        data=df,
        x="ln_scopus_docs",
        y="pct_q1",
        hue="tier",
        palette=palette,
        alpha=0.65,
        s=60,
        ax=ax
    )

    for tier_name, color in palette.items():
        sub = df[df["tier"] == tier_name]
        sns.regplot(
            data=sub,
            x="ln_scopus_docs",
            y="pct_q1",
            scatter=False,
            ax=ax,
            color=color,
            line_kws={"linewidth": 2, "linestyle": "-", "label": f"{tier_name} Fit"}
        )

    ax.set_title("Figure 6: Testing Quality Dilution: Publication Volume vs. Q1 Journal Share", fontsize=13, pad=12, weight="bold")
    ax.set_xlabel("ln(Annual Scopus Publication Volume)", fontsize=11, labelpad=8)
    ax.set_ylabel("Share of Q1 Publications (%)", fontsize=11, labelpad=8)
    ax.set_ylim(-2, 102)
    ax.legend(title="", frameon=True, facecolor="white", edgecolor="none")
    plt.tight_layout()

    out_path = FIGURES_DIR / "fig6_volume_vs_q1_dilution_test.png"
    plt.savefig(out_path)
    plt.close()
    print(f"Saved: {out_path}")


def plot_fig7_top_q1_performers(df: pd.DataFrame):
    """Figure 7: Top 15 Universities by 5-Year Average Q1 Publication Share."""
    avg_q1 = df.groupby("name_canonical")["pct_q1"].mean().sort_values(ascending=False).head(15).reset_index()
    avg_q1["short_name"] = avg_q1["name_canonical"].apply(lambda x: x.split(",")[0].strip()[:35])

    fig, ax = plt.subplots(figsize=(10, 6.5), dpi=300)
    sns.barplot(
        data=avg_q1,
        x="pct_q1",
        y="short_name",
        hue="short_name",
        palette="Blues_r",
        legend=False,
        ax=ax,
        edgecolor="#333333",
        linewidth=0.6
    )

    for i, v in enumerate(avg_q1["pct_q1"]):
        ax.text(v + 0.8, i, f"{v:.1f}%", va="center", fontsize=9, weight="bold")

    ax.set_title("Figure 7: Top 15 Indian Universities by 5-Year Average Q1 Journal Share (2021–2025)", fontsize=12, pad=12, weight="bold")
    ax.set_xlabel("Average Q1 Publication Share (%)", fontsize=11)
    ax.set_ylabel("")
    ax.set_xlim(0, 75)
    plt.tight_layout()

    out_path = FIGURES_DIR / "fig7_top_q1_universities.png"
    plt.savefig(out_path)
    plt.close()
    print(f"Saved: {out_path}")


def main():
    print("=" * 80)
    print("PART B: JOURNAL-QUALITY CHANNEL & GAMING ANALYSIS (SCImago Q1-Q4)")
    print("=" * 80)

    raw_df = load_panel()
    df = prepare_part_b_data(raw_df)
    print(f"Panel prepared: {len(df)} rows across {df['institute_id'].nunique()} institutions.")

    # 1. Table B1: 5-Year Quartile Trends
    print("\n--- Generating Table B1: 5-Year Quartile Trends by Tier ---")
    t_b1 = generate_table_b1_trends(df)
    print(t_b1[["Year", "Sample", "Mean Scopus Volume", "Mean % Q1", "Mean % Q2", "Mean % Q3", "Mean % Q4"]].to_string(index=False))

    # 2. Table B2: Model B1 - Q1 Dilution Regressions
    print("\n--- Estimating Model B1: Volume-Quality Trade-Off (% Q1) ---")
    t_b2, h_text = run_model_b1_q1_regressions(df)
    print(t_b2.to_string(index=False))
    print(f"\nDiagnostics: {h_text}")

    # 3. Table B3: Model B1b - Multiple Thresholds
    print("\n--- Estimating Model B1b: Multiple Quartile Thresholds (Two-Way FE) ---")
    t_b3 = run_model_b1b_high_vs_low_regressions(df)
    print(t_b3.to_string(index=False))

    # 4. Table B4: Model B2 - Subgroup Quality Dynamics (Tier 1 vs Tier 2)
    print("\n--- Estimating Model B2: Subgroup Quality Dynamics (Tier 1 vs Tier 2) ---")
    t_b4 = run_model_b2_subgroup_quality(df)
    print(t_b4.to_string(index=False))

    # 5. Visualizations
    print("\n--- Generating Part B Figures ---")
    plot_fig5_quartile_stacked_distribution(df)
    plot_fig6_volume_vs_quality(df)
    plot_fig7_top_q1_performers(df)

    print("\n" + "=" * 80)
    print("Part B Analysis & Visualizations Complete! Results in analysis/results/")
    print("=" * 80)


if __name__ == "__main__":
    main()
