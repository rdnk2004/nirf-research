"""
Part A: Visualizations & Subgroup Heterogeneity Analysis

This module produces:
1. Publication-ready visualization plots (saved in analysis/results/figures/):
   - Fig 1: PhD Scholars vs. Scopus Research Output (Scatter + Trend)
   - Fig 2: Teaching Resources vs. Graduate Placement Rate (by Rank Tier)
   - Fig 3: 5-Year Longitudinal Trajectories (2021-2025) across Tiers
   - Fig 4: Correlation Heatmap of Part A Variables
2. Subgroup Heterogeneity Panel Regressions:
   - Tier 1 (Rank 1-35) vs. Tier 2 (Rank 36-70) Two-Way Fixed Effects models
   - Tests whether resource payoffs differ between elite and emerging universities.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from linearmodels.panel import PanelOLS

from analysis.common import load_panel
from analysis.option_a_regression import prepare_part_a_data, format_panel_results

FIGURES_DIR = Path("analysis/results/figures")
FIGURES_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR = Path("analysis/results")

# Set aesthetic style for publication
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.sans-serif"] = "DejaVu Sans"
plt.rcParams["axes.edgecolor"] = "#333333"
plt.rcParams["axes.linewidth"] = 0.8


def assign_rank_tiers(df: pd.DataFrame) -> pd.DataFrame:
    """Assign institutions to Tier 1 (Rank 1-35) or Tier 2 (Rank 36-70) based on 5-year median rank."""
    df = df.copy()
    median_rank = df.groupby("institute_id")["rank"].median()
    tier_map = {iid: ("Tier 1 (Rank 1-35)" if r <= 35 else "Tier 2 (Rank 36-70)") for iid, r in median_rank.items()}
    df["tier"] = df["institute_id"].map(tier_map)
    return df


def plot_phd_vs_research(df: pd.DataFrame):
    """Figure 1: PhD Scholars vs. Scopus Research Output."""
    fig, ax = plt.subplots(figsize=(9, 6), dpi=300)

    palette = {"Tier 1 (Rank 1-35)": "#1f77b4", "Tier 2 (Rank 36-70)": "#ff7f0e"}

    sns.scatterplot(
        data=df,
        x="ln_phd_scholars",
        y="ln_scopus_docs",
        hue="tier",
        palette=palette,
        alpha=0.65,
        s=55,
        ax=ax
    )

    # Linear trend line
    sns.regplot(
        data=df,
        x="ln_phd_scholars",
        y="ln_scopus_docs",
        scatter=False,
        ax=ax,
        color="#2ca02c",
        line_kws={"linewidth": 2, "linestyle": "--", "label": "Overall Trend"}
    )

    # Label prominent universities (2025 data points)
    df_2025 = df[df["year"] == 2025]
    notable_names = [
        "Indian Institute of Science",
        "Jawaharlal Nehru University",
        "Banaras Hindu University",
        "Anna University",
        "Jamia Millia Islamia",
        "Manipal Academy of Higher Education",
        "Aligarh Muslim University"
    ]
    for _, row in df_2025.iterrows():
        name = row["name_canonical"]
        if any(target.lower() in name.lower() for target in notable_names):
            short_name = name.split(",")[0].strip()
            ax.annotate(
                short_name,
                (row["ln_phd_scholars"], row["ln_scopus_docs"]),
                fontsize=8,
                alpha=0.85,
                xytext=(5, 4),
                textcoords="offset points",
                weight="bold"
            )

    ax.set_title("Figure 1: Doctoral Scholars vs. Research Output (70 Universities, 2021–2025)", fontsize=13, pad=12, weight="bold")
    ax.set_xlabel("ln(Full-Time PhD Scholars + 1)", fontsize=11, labelpad=8)
    ax.set_ylabel("ln(Annual Scopus Publications)", fontsize=11, labelpad=8)
    ax.legend(title="", frameon=True, facecolor="white", edgecolor="none")
    plt.tight_layout()

    out_path = FIGURES_DIR / "fig1_phd_vs_scopus_output.png"
    plt.savefig(out_path)
    plt.close()
    print(f"Saved: {out_path}")


def plot_faculty_vs_placement(df: pd.DataFrame):
    """Figure 2: Faculty Resources vs. Placement Rate."""
    fig, ax = plt.subplots(figsize=(9, 6), dpi=300)

    palette = {"Tier 1 (Rank 1-35)": "#1f77b4", "Tier 2 (Rank 36-70)": "#ff7f0e"}

    sns.scatterplot(
        data=df,
        x="faculty_per_100_students",
        y="placement_rate_pct",
        hue="tier",
        palette=palette,
        alpha=0.65,
        s=55,
        ax=ax
    )

    # Trend lines per tier
    for tier_name, color in palette.items():
        sub = df[df["tier"] == tier_name]
        sns.regplot(
            data=sub,
            x="faculty_per_100_students",
            y="placement_rate_pct",
            scatter=False,
            ax=ax,
            color=color,
            line_kws={"linewidth": 1.8, "linestyle": "-", "label": f"{tier_name} Fit"}
        )

    ax.set_title("Figure 2: Faculty Strength vs. Graduate Placement Rate (2021–2025)", fontsize=13, pad=12, weight="bold")
    ax.set_xlabel("Faculty per 100 Students", fontsize=11, labelpad=8)
    ax.set_ylabel("Placement Rate (%)", fontsize=11, labelpad=8)
    ax.set_ylim(0, 105)
    ax.legend(title="", frameon=True, facecolor="white", edgecolor="none")
    plt.tight_layout()

    out_path = FIGURES_DIR / "fig2_faculty_vs_placement_rate.png"
    plt.savefig(out_path)
    plt.close()
    print(f"Saved: {out_path}")


def plot_5year_trajectories(df: pd.DataFrame):
    """Figure 3: 5-Year Trajectories of Research and Placement across Tiers."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5), dpi=300)

    # 1. Median Scopus Documents over time
    med_scopus = df.groupby(["year", "tier"])["scopus_total_documents"].median().reset_index()
    sns.lineplot(
        data=med_scopus,
        x="year",
        y="scopus_total_documents",
        hue="tier",
        marker="o",
        markersize=8,
        linewidth=2.5,
        palette={"Tier 1 (Rank 1-35)": "#1f77b4", "Tier 2 (Rank 36-70)": "#ff7f0e"},
        ax=ax1
    )
    ax1.set_title("Panel A: Median Annual Scopus Publications", fontsize=11, weight="bold")
    ax1.set_xlabel("Year", fontsize=10)
    ax1.set_ylabel("Median Publications", fontsize=10)
    ax1.set_xticks([2021, 2022, 2023, 2024, 2025])
    ax1.legend(title="")

    # 2. Median Placement Rate over time
    med_place = df.groupby(["year", "tier"])["placement_rate_pct"].median().reset_index()
    sns.lineplot(
        data=med_place,
        x="year",
        y="placement_rate_pct",
        hue="tier",
        marker="s",
        markersize=8,
        linewidth=2.5,
        palette={"Tier 1 (Rank 1-35)": "#1f77b4", "Tier 2 (Rank 36-70)": "#ff7f0e"},
        ax=ax2
    )
    ax2.set_title("Panel B: Median Placement Rate (%)", fontsize=11, weight="bold")
    ax2.set_xlabel("Year", fontsize=10)
    ax2.set_ylabel("Median Placement Rate (%)", fontsize=10)
    ax2.set_xticks([2021, 2022, 2023, 2024, 2025])
    ax2.legend(title="")

    fig.suptitle("Figure 3: 5-Year Evolution of University Performance by Rank Tier (2021–2025)", fontsize=13, weight="bold", y=1.02)
    plt.tight_layout()

    out_path = FIGURES_DIR / "fig3_5year_trajectories_by_tier.png"
    plt.savefig(out_path)
    plt.close()
    print(f"Saved: {out_path}")


def plot_correlation_heatmap(df: pd.DataFrame):
    """Figure 4: Correlation Heatmap of Key Part A Variables."""
    cols = [
        "ln_scopus_docs",
        "placement_rate_pct",
        "faculty_per_100_students",
        "ln_phd_scholars",
        "ln_total_students",
        "ln_sponsored_amount",
        "higher_studies_rate_pct"
    ]
    labels = [
        "ln(Scopus Docs)",
        "Placement Rate (%)",
        "Faculty / 100 Students",
        "ln(PhD Scholars)",
        "ln(Total Students)",
        "ln(Funding)",
        "Higher Studies (%)"
    ]

    corr = df[cols].corr()
    corr.index = labels
    corr.columns = labels

    fig, ax = plt.subplots(figsize=(8, 7), dpi=300)
    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
    cmap = sns.diverging_palette(220, 20, as_cmap=True)

    sns.heatmap(
        corr,
        mask=mask,
        annot=True,
        fmt=".2f",
        cmap=cmap,
        vmin=-0.6,
        vmax=0.8,
        center=0,
        square=True,
        linewidths=0.5,
        cbar_kws={"shrink": 0.8, "label": "Pearson Correlation Coefficient"},
        ax=ax
    )

    ax.set_title("Figure 4: Correlation Matrix of Part A Variables (N = 350)", fontsize=13, pad=15, weight="bold")
    plt.tight_layout()

    out_path = FIGURES_DIR / "fig4_correlation_heatmap.png"
    plt.savefig(out_path)
    plt.close()
    print(f"Saved: {out_path}")


def run_subgroup_regressions(df: pd.DataFrame) -> pd.DataFrame:
    """Run Two-Way Fixed Effects regressions separately for Tier 1 vs. Tier 2."""
    df_p = df.set_index(["institute_id", "year"])

    # 1. Model A1 (Research Output): ln_scopus_docs
    x_res = ["faculty_per_100_students", "ln_phd_scholars", "ln_total_students", "ln_sponsored_amount"]

    # Full Panel TWFE
    m_all_res = PanelOLS(df_p["ln_scopus_docs"], df_p[x_res], entity_effects=True, time_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )
    m_all_res._entity_effects = True
    m_all_res._time_effects = True

    # Tier 1 (Rank 1-35)
    t1_p = df_p[df_p["tier"] == "Tier 1 (Rank 1-35)"]
    m_t1_res = PanelOLS(t1_p["ln_scopus_docs"], t1_p[x_res], entity_effects=True, time_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )
    m_t1_res._entity_effects = True
    m_t1_res._time_effects = True

    # Tier 2 (Rank 36-70)
    t2_p = df_p[df_p["tier"] == "Tier 2 (Rank 36-70)"]
    m_t2_res = PanelOLS(t2_p["ln_scopus_docs"], t2_p[x_res], entity_effects=True, time_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )
    m_t2_res._entity_effects = True
    m_t2_res._time_effects = True

    # 2. Model A2 (Student Placement): placement_rate_pct
    # NOTE: higher_studies_rate_pct removed as a predictor -- it shares
    # the same total_graduating denominator as placement_rate_pct, so it
    # was predicting placement with a mechanically related variable
    # rather than a genuinely independent one. See
    # run_model_a2_placement's docstring in option_a_regression.py.
    x_plc = ["faculty_per_100_students", "ln_total_students"]

    m_all_plc = PanelOLS(df_p["placement_rate_pct"], df_p[x_plc], entity_effects=True, time_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )
    m_all_plc._entity_effects = True
    m_all_plc._time_effects = True

    m_t1_plc = PanelOLS(t1_p["placement_rate_pct"], t1_p[x_plc], entity_effects=True, time_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )
    m_t1_plc._entity_effects = True
    m_t1_plc._time_effects = True

    m_t2_plc = PanelOLS(t2_p["placement_rate_pct"], t2_p[x_plc], entity_effects=True, time_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )
    m_t2_plc._entity_effects = True
    m_t2_plc._time_effects = True

    models = {
        "Research: Full Sample": m_all_res,
        "Research: Tier 1 (1-35)": m_t1_res,
        "Research: Tier 2 (36-70)": m_t2_res,
        "Placement: Full Sample": m_all_plc,
        "Placement: Tier 1 (1-35)": m_t1_plc,
        "Placement: Tier 2 (36-70)": m_t2_plc,
    }

    subgroup_table = format_panel_results(models)
    out_file = RESULTS_DIR / "part_a_table5_subgroup_heterogeneity.csv"
    subgroup_table.to_csv(out_file, index=False)
    print(f"\nSaved Subgroup Table: {out_file}")
    return subgroup_table


def main():
    print("=" * 80)
    print("PART A: VISUALIZATIONS & SUBGROUP HETEROGENEITY PIPELINE")
    print("=" * 80)

    raw_df = load_panel()
    df = prepare_part_a_data(raw_df)
    df = assign_rank_tiers(df)

    print(f"Dataset ready. Tier distribution: {df['tier'].value_counts().to_dict()}")

    print("\n--- Generating Visualizations ---")
    plot_phd_vs_research(df)
    plot_faculty_vs_placement(df)
    plot_5year_trajectories(df)
    plot_correlation_heatmap(df)

    print("\n--- Running Subgroup Heterogeneity Regressions (Tier 1 vs. Tier 2) ---")
    sub_table = run_subgroup_regressions(df)
    print("\nSubgroup Regressions (Two-Way Fixed Effects):")
    print(sub_table.to_string(index=False))

    print("\n" + "=" * 80)
    print("Visualizations & Subgroup Analysis Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()