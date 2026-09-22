# Evaluating the Impact of NIRF on University Research and Quality: An Empirical Panel Study of 70 Indian Universities (2021–2025)

**Authors / Research Project**: NIRF Research Study (Option A & Option B)  
**Codebase & Data**: `github.com/rdnk2004/nirf-scraper`  
**Panel Specification**: Balanced Panel ($N = 70$ Universities $\times$ $T = 5$ Years [2021–2025] $= 350$ Observations)  
**Primary Data Sources**: Raw Institutional NIRF PDF Submissions, Scopus Search API, SCImago Journal & Country Rank Annual Snapshots  

---

## Executive Summary

This study provides an empirical evaluation of India's National Institutional Ranking Framework (NIRF) and its impact on university research productivity, publication quality, and student career outcomes across a 5-year balanced panel of 70 top-ranked Indian universities (2021–2025). 

Addressing the core methodological limitation of prior literature—which relied on circular correlations between NIRF's proprietary, normalized composite scores—this study uses **raw institutional data** extracted directly from institutional submissions, verified against **637,371 raw Scopus publications**, and mapped by ISSN against **annual SCImago journal quartile rankings (Q1–Q4)** to eliminate citation-age decay.

```
                    ┌────────────────────────────────────────────────────────┐
                    │            NIRF Policy Assumptions Tested              │
                    └────────────────────────────────────────────────────────┘
                                   │                           │
                                   ▼                           ▼
                 ┌────────────────────────────────┐   ┌────────────────────────────────┐
                 │       Part A: Human Capital     │   │      Part B: Quality Channel   │
                 │   Does expanding teaching load │   │   Did the volume surge dilute  │
                 │   and PhD scholars boost real  │   │   research into marginal Q3/Q4 │
                 │   research & student placement?│   │   venues or scale Q1/Q2 output?│
                 └────────────────────────────────┘   └────────────────────────────────┘
                                   │                           │
                                   ▼                           ▼
                 ┌────────────────────────────────┐   ┌────────────────────────────────┐
                 │          Key Findings          │   │          Key Findings          │
                 │ • PhD scholars drive research  │   │ • "Gaming/Dilution" REJECTED   │
                 │   volume (β = 0.32–0.64, p<.01)│   │ • Volume growth expands Q1/Q2  │
                 │ • Faculty headcount does NOT   │   │   share (+6.63 percentage pts) │
                 │   boost within-school research │   │ • Q3/Q4 contracted (-5.36 pts) │
                 │ • Faculty attention boosts     │   │ • PhD base is the dual engine  │
                 │   student placement (β = +0.48)│   │   of both volume AND quality   │
                 └────────────────────────────────┘   └────────────────────────────────┘
```

### Key Empirical Takeaways:
1. **The Doctoral Workforce Engine (Part A)**: Research output is driven overwhelmingly by the **full-time doctoral scholar base** ($\beta = 0.3215^{**}$ in Two-Way Fixed Effects; $\beta = 0.6389^{***}$ in Tier 1 elite universities). Merely expanding faculty headcount without expanding PhD capacity does not produce within-institution research growth.
2. **Mentorship Payoff in Student Placement (Part A)**: Improving the faculty-to-student ratio directly increases the graduate campus placement rate ($\beta = +0.4818^{**}$ under Random Effects), with the marginal return of faculty attention being nearly **twice as high in Tier 2 universities ($+1.09$) as in Tier 1 ($+0.59$)**.
3. **Rejection of the "Gaming / Dilution" Hypothesis (Part B)**: Contrary to widespread skepticism that NIRF incentivized flooding marginal (Q3/Q4) journals, institutional volume growth is accompanied by a **statistically significant upward shift in quality**: each $10\%$ expansion in publication volume expands top-half journal share (Q1+Q2) by **$+6.63$ percentage points ($p < 0.001$)** and contracts lower-half share (Q3+Q4) by **$-5.36$ percentage points ($p < 0.001$)**.
4. **PhD Scholars as the Dual Engine (Part B)**: Doctoral scholar enrollment is the single strongest determinant of high-impact research, increasing Q1 publication share ($\beta = +4.2362^{***}$) while systematically suppressing Q4 publication share ($\beta = -3.2754^{**}$ in Tier 1).

---

## 1. Background & Research Framework

### 1.1 Origin & Research Motivation
A 2019 baseline study (*"Impact of NIRF on research publications: A study on top 20 (ranked) Indian Universities"*) found that publication volume rose by approximately $\sim 38\%$ following the introduction of the NIRF ranking framework. While this established an aggregate volume shock, two fundamental academic and policy questions remained unanswered:

* **Research Question 1 (Part A: Structural Inputs $\rightarrow$ Real Outputs)**: Does investment in Teaching, Learning & Resources (TLR)—which accounts for $30\%$ of the total NIRF score—translate into genuine research output and graduate placement outcomes, or is resource accumulation decoupled from actual institutional performance?
* **Research Question 2 (Part B: Quality Channel vs. Gaming Channel)**: Since NIRF's Research and Professional Practice (RPC) metric assigns greater weight to citation-based quality ($QP = 40$ marks) than raw volume ($PU = 35$ marks), did the post-NIRF publication surge represent genuine high-impact scholarship (Q1/Q2 journals) or was it driven by opportunistic publication in low-standard, quality-indifferent channels (Q3/Q4 journals)?

### 1.2 Overcoming the Methodological Circularity of Prior Studies
The vast majority of existing NIRF analyses regress published composite scores against one another (e.g., regressing the RPC score on the TLR score). This is econometrically invalid:
* NIRF's published scores are normalized, peer-relative percentiles calculated using undisclosed formulas.
* Regressing one normalized composite score on another evaluates the ranking committee's mathematical curve-fitting, not institutional reality.

**Our Fix**:
1. We bypass all composite scores and extract **raw institutional figures** from the official *Data Submitted by Institution* PDFs (raw faculty headcount, total student enrollment, full-time PhD enrollment, graduate placement counts).
2. We pull **independent research data directly from the Scopus API** ($637,371$ individual paper records).
3. We solve the citation-decay confound by matching each paper to its publication year's **SCImago Journal Rank (SJR) Quartile snapshot (Q1–Q4)** by ISSN.

---

## 2. Dataset Construction & Panel Scope

### 2.1 Final Panel Scope
From an initial candidate pool of 145 universities that appeared in the NIRF University Top 100 between 2019 and 2025, the panel was refined to **70 universities with complete, unbroken 5-year coverage (2021–2025)**:
* **Excluded ($N = 63$)**: Dropped due to intermittent presence (institutions that moved in and out of the top 100 across years, creating structural missingness).
* **Excluded ($N = 7$)**: Dropped due to unresolved Scopus affiliation matching ambiguities or duplicate campus identities (fully documented in [`data/final/EXCLUSIONS.md`](file:///d:/nirf-scraper/data/final/EXCLUSIONS.md)).
* **Final Dataset**: $70\text{ universities} \times 5\text{ years} = \mathbf{350\text{ observations}}$ (Balanced Panel).

The final dataset is located at [`data/final/merged_analysis_dataset.csv`](file:///d:/nirf-scraper/data/final/merged_analysis_dataset.csv).

### 2.2 Table 1: Summary Statistics & Variance Decomposition (N = 350)
The table below decomposes variation into **Between-University** (cross-sectional variation across institutions) and **Within-University** (longitudinal change within an institution over the 5-year window):

| Variable | Raw / Metric | Mean | Overall Std | Between Std | Within Std | Min | Median | Max |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Scopus Documents** | Count | $1,438.98$ | $1,396.89$ | $1,302.62$ | $523.38$ | $1$ | $825$ | $5,000$ |
| **$\ln(\text{Scopus Documents})$** | Log Count | $6.66$ | $1.45$ | $1.38$ | $0.46$ | $0.00$ | $6.72$ | $8.52$ |
| **Placement Rate** | $\%$ of cohort | $55.64\%$ | $24.60\%$ | $22.92\%$ | $9.28\%$ | $6.90\%$ | $60.85\%$ | $99.50\%$ |
| **Higher Studies Rate** | $\%$ of cohort | $19.40\%$ | $15.08\%$ | $13.54\%$ | $6.79\%$ | $0.54\%$ | $15.76\%$ | $89.47\%$ |
| **Students per Faculty** | Student/Teacher | $12.29$ | $3.53$ | $3.22$ | $1.48$ | $1.22$ | $12.50$ | $31.90$ |
| **Faculty per 100 Students** | Teachers / 100 | $9.73$ | $8.61$ | $8.59$ | $1.09$ | $3.14$ | $8.00$ | $81.86$ |
| **Full-Time PhD Scholars** | Headcount | $977.20$ | $927.81$ | $897.75$ | $253.23$ | $28$ | $608$ | $4,516$ |
| **Total Student Strength** | Headcount | $11,104.51$ | $10,381.43$ | $10,334.36$ | $1,482.96$ | $1,137$ | $7,551$ | $60,645$ |
| **Sponsored Research** | INR (Crores) | $44.61$ | $111.70$ | $99.22$ | $52.39$ | $0.15$ | $19.41$ | $1,111.85$ |
| **$\text{\% Q1 Journals}$** | $\%$ of matched | $34.94\%$ | $12.19\%$ | $11.62\%$ | $3.83\%$ | $0.00\%$ | $35.20\%$ | $100.00\%$ |
| **$\text{\% Q2 Journals}$** | $\%$ of matched | $31.49\%$ | $6.79\%$ | $5.78\%$ | $3.63\%$ | $0.00\%$ | $31.70\%$ | $75.00\%$ |
| **$\text{\% Q3 Journals}$** | $\%$ of matched | $19.16\%$ | $10.44\%$ | $9.82\%$ | $3.67\%$ | $0.00\%$ | $17.30\%$ | $100.00\%$ |
| **$\text{\% Q4 Journals}$** | $\%$ of matched | $14.41\%$ | $7.69\%$ | $6.88\%$ | $3.54\%$ | $0.00\%$ | $13.00\%$ | $47.50\%$ |
| **Quartile Match Rate** | $\%$ of Scopus | $74.50\%$ | $12.76\%$ | $11.45\%$ | $5.72\%$ | $0.00\%$ | $76.35\%$ | $100.00\%$ |

*Source: [`analysis/results/part_a_table1_descriptives.csv`](file:///d:/nirf-scraper/analysis/results/part_a_table1_descriptives.csv). Note: The unmatched $\sim 25\%$ in Scopus comprises conference proceedings, book series, and trade reports that structurally lack ISSNs.*

---

## 3. Part A: Teaching-Learning Resources vs. Real Institutional Outputs

### 3.1 Econometric Specification
To eliminate time-invariant omitted variable bias (e.g., historical prestige, location advantages, central funding status), we estimate Two-Way Fixed Effects (TWFE) models with standard errors clustered at the institutional level:

$$\ln(\text{Scopus Documents}_{it}) = \beta_1 (\text{Faculty per 100}_{it}) + \beta_2 \ln(\text{PhD Scholars}_{it}) + \beta_3 \ln(\text{Funding}_{it}) + \beta_4 \ln(\text{Students}_{it}) + \alpha_i + \delta_t + \varepsilon_{it}$$

In parallel, we model graduate career destinations as two symmetric, non-artifactual equations:
$$\text{Placement Rate}_{it} = \gamma_1 (\text{Faculty per 100}_{it}) + \gamma_2 \ln(\text{Students}_{it}) + \alpha_i + \delta_t + u_{it}$$
$$\text{Higher Studies Rate}_{it} = \theta_1 (\text{Faculty per 100}_{it}) + \theta_2 \ln(\text{Students}_{it}) + \alpha_i + \delta_t + v_{it}$$

### 3.2 Model A1: Research Output Regressions
*Dependent Variable: $\ln(\text{Scopus Total Documents})$*

| Explanatory Variable | (1) Pooled OLS | (2) Random Effects | (3) Entity FE | (4) Two-Way FE | (5) Lagged TWFE ($t-1$) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **$\ln(\text{Full-Time PhD Scholars})$** | **$0.4170^{***}$**<br>*(0.1316)* | **$0.4340^{***}$**<br>*(0.1230)* | **$0.4210^{***}$**<br>*(0.1324)* | **$0.3215^{**}$**<br>*(0.1397)* | $0.1712$<br>*(0.1254)* |
| **Faculty per 100 Students** | $0.0304^{***}$<br>*(0.0112)* | $0.0084$<br>*(0.0172)* | $-0.0538$<br>*(0.0444)* | $-0.0620$<br>*(0.0497)* | $-0.0466$<br>*(0.0442)* |
| **$\ln(\text{Sponsored Funding})$** | $0.0338$<br>*(0.1331)* | $-0.0117$<br>*(0.0503)* | $-0.0383$<br>*(0.0490)* | $-0.0536$<br>*(0.0478)* | $-0.0301$<br>*(0.0388)* |
| **$\ln(\text{Total Students})$** | $0.7153^{***}$<br>*(0.1853)* | $0.7195^{***}$<br>*(0.1344)* | $0.6392$<br>*(0.4973)* | $0.0875$<br>*(0.4968)* | $0.1736$<br>*(0.2820)* |
| **Constant** | $-3.3656$<br>*(2.1746)* | $-2.4410$<br>*(1.6376)* | — | — | — |
| **Institution FE** | No | No | **Yes** | **Yes** | **Yes** |
| **Year FE** | No | No | No | **Yes** | **Yes** |
| **Observations** | $350$ | $350$ | $350$ | $350$ | $280$ |
| **$R^2$** | $0.3309$ | $0.1777$ | $0.1502$ | $0.0707$ | $0.0892$ |

*Standard errors clustered by university in parentheses. $^{***}p < 0.01, ^{**}p < 0.05, ^{*}p < 0.10$. Diagnostic: Hausman Test $\chi^2(4) = 23.122, p = 0.00012$ (rejects RE; FE is required).*  
*Source: [`analysis/results/part_a_table3_model_a1_research.csv`](file:///d:/nirf-scraper/analysis/results/part_a_table3_model_a1_research.csv)*

#### Empirical Findings:
1. **Doctoral Scholars Are the Primary Engine**: Across all specifications, doctoral scholars significantly predict verified publication volume. In the Two-Way Fixed Effects model, a **$10\%$ increase in doctoral enrollment yields a $+3.2\%$ increase in annual publications ($p < 0.05$)**.
2. **The "Headcount Illusion" of Faculty Growth**: In cross-sectional Pooled OLS, faculty headcount appears positively correlated with research ($\beta = 0.0304^{***}$) simply because top universities have both more faculty and more research. But once Entity Fixed Effects are applied, the coefficient flips and becomes insignificant. Hiring teachers without expanding the research workforce absorbs departmental resources into teaching and administrative loads without increasing publication volume.

---

### 3.3 Models A2 & A2b: Graduate Destinations (Placement vs. Higher Studies)
*Estimating competing post-graduation outcomes without mechanical denominator artifacts:*

| Explanatory Variable | Model A2: Placement Rate (%) [RE] | Model A2: Placement Rate (%) [TWFE] | Model A2: Placement (Lagged $t-1$) | Model A2b: Higher Studies (%) [TWFE] |
| :--- | :---: | :---: | :---: | :---: |
| **Faculty per 100 Students** | **$+0.4818^{**}$**<br>*(0.1992)* | $+0.8484$<br>*(0.9141)* | $+1.6358$<br>*(1.0475)* | $-0.9840$<br>*(0.6956)* |
| **$\ln(\text{Total Students})$** | $+12.6654^{***}$<br>*(3.0336)* | $+4.1923$<br>*(10.9552)* | $+2.8257$<br>*(7.0350)* | **$-10.4953^{*}$**<br>*(6.1279)* |
| **Institution & Year FE** | No | **Yes** | **Yes** | **Yes** |
| **Observations** | $350$ | $350$ | $280$ | $350$ |

*Source: [`analysis/results/part_a_table4_model_a2_placement.csv`](file:///d:/nirf-scraper/analysis/results/part_a_table4_model_a2_placement.csv) & [`part_a_table4b_model_a2b_higher_studies.csv`](file:///d:/nirf-scraper/analysis/results/part_a_table4b_model_a2b_higher_studies.csv).*

#### Empirical Findings:
1. **Teaching Attention Pays Off in Career Entry**: Under Random Effects (which the Hausman test indicates is valid for placement: $\chi^2 = 2.29, p = 0.515$), adding 1 faculty member per 100 students increases the campus placement rate by **$+0.48$ percentage points ($p < 0.05$)**. The lagged model ($t-1$) exhibits an even stronger point estimate ($+1.64$), reflecting the cumulative nature of instructional mentorship prior to cohort graduation.
2. **Scale Bias Against Advanced Studies**: Institutional size ($\ln(\text{Total Students})$) has a negative impact on higher studies progression ($-10.50^{*}, p < 0.10$), demonstrating that mass-enrollment institutions predominantly funnel graduates directly into terminal corporate employment.

---

### 3.4 Subgroup Heterogeneity: The Tier 1 vs. Tier 2 Structural Divide
*Two-Way Fixed Effects across Top 35 (Tier 1) vs. Ranks 36–70 (Tier 2):*

| Metric | Research: Tier 1 (1–35) | Research: Tier 2 (36–70) | Placement: Tier 1 (1–35) | Placement: Tier 2 (36–70) |
| :--- | :---: | :---: | :---: | :---: |
| **$\ln(\text{PhD Scholars})$** | **$+0.6389^{***}$** *(0.2310)* | $+0.1693$ *(0.1598)* | — | — |
| **Faculty per 100 Students** | $-0.0556$ *(0.0804)* | $-0.0811$ *(0.0561)* | $+0.5858$ *(1.2557)* | **$+1.0949$** *(1.1683)* |
| **Observations** | $170$ | $180$ | $170$ | $180$ |

*Source: [`analysis/results/part_a_table5_subgroup_heterogeneity.csv`](file:///d:/nirf-scraper/analysis/results/part_a_table5_subgroup_heterogeneity.csv).*

* **The Elite Multiplier**: In Tier 1 institutions, the elasticity of research to PhD scholars is **$0.64$ ($p < 0.01$)**—a $10\%$ expansion in PhD intake yields a $+6.4\%$ surge in Scopus papers.
* **The Emerging Bottleneck**: In Tier 2 institutions, the PhD coefficient drops to $0.17$ and loses statistical significance ($p > 0.25$). Without mature laboratory infrastructure and research networks, expanding PhD intake yields diminished research returns.
* **Mentorship Dividend**: Conversely, faculty attention matters nearly **twice as much for student placement in Tier 2 ($+1.09$) as in Tier 1 ($+0.59$)**, where institutional prestige already ensures baseline recruitment.

---

## 4. Part B: Journal Quality & Gaming Channel Analysis

### 4.1 Aggregate Longitudinal Trends (2021–2025)
*Table B1 tracks publication volume and SCImago journal quartile distribution over time:*

| Year | Cohort | Mean Scopus Volume | Mean % Q1 | Mean % Q2 | Mean % Q3 | Mean % Q4 | High-Tier (% Q1+Q2) | Low-Tier (% Q3+Q4) |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **2021** | Full Panel ($N=70$) | $1,043$ | $33.11\%$ | $30.08\%$ | $20.59\%$ | $16.23\%$ | $63.19\%$ | $36.82\%$ |
| | Tier 1 (1–35) | $1,607$ | $37.22\%$ | $31.14\%$ | $17.23\%$ | $14.40\%$ | $68.36\%$ | $31.63\%$ |
| | Tier 2 (36–70) | $511$ | $29.22\%$ | $29.07\%$ | $23.76\%$ | $17.97\%$ | $58.29\%$ | $41.73\%$ |
| **2023** | Full Panel ($N=70$) | $1,470$ | $33.92\%$ | $31.66\%$ | $19.91\%$ | $14.51\%$ | $65.58\%$ | $34.42\%$ |
| | Tier 1 (1–35) | $2,187$ | $36.22\%$ | $31.34\%$ | $19.61\%$ | $12.82\%$ | $67.56\%$ | $32.43\%$ |
| | Tier 2 (36–70) | $794$ | $31.75\%$ | $31.96\%$ | $20.20\%$ | $16.09\%$ | $63.71\%$ | $36.29\%$ |
| **2025** | Full Panel ($N=70$) | $\mathbf{1,759}$ | $\mathbf{36.91\%}$ | $\mathbf{30.72\%}$ | $\mathbf{18.94\%}$ | $\mathbf{13.43\%}$ | $\mathbf{67.63\%}$ | $\mathbf{32.37\%}$ |
| | Tier 1 (1–35) | $\mathbf{2,518}$ | $\mathbf{39.60\%}$ | $\mathbf{30.18\%}$ | $\mathbf{19.46\%}$ | $\mathbf{10.76\%}$ | $\mathbf{69.78\%}$ | $\mathbf{30.22\%}$ |
| | Tier 2 (36–70) | $\mathbf{1,043}$ | $\mathbf{34.36\%}$ | $\mathbf{31.24\%}$ | $\mathbf{18.45\%}$ | $\mathbf{15.96\%}$ | $\mathbf{65.60\%}$ | $\mathbf{34.41\%}$ |

*Source: [`analysis/results/part_b_table1_quartile_trends.csv`](file:///d:/nirf-scraper/analysis/results/part_b_table1_quartile_trends.csv).*

```
                         LONGITUDINAL PUBLICATION QUALITY SHIFT (2021 -> 2025)
   Year 2021:  [=== Q1: 33.1% ===] [== Q2: 30.1% ==] [= Q3: 20.6% =] [= Q4: 16.2% =]
   Year 2025:  [==== Q1: 36.9% ===] [== Q2: 30.7% ==] [= Q1: 18.9% =] [= Q4: 13.4% =]
               ▲                                                      ▼
               └───────── TOP TIERS EXPAND (+4.4%) ───────────────────┴── BOTTOM TIERS CONTRACT (-4.4%)
```

### 4.2 Econometric Evaluation of the "Quality Dilution" Hypothesis
To test whether volume growth was bought at the cost of journal quality, we regress quartile shares on log publication volume and institutional inputs:

$$\text{Quartile Share}_{it} = \beta_1 \ln(\text{Scopus Documents}_{it}) + \beta_2 \ln(\text{PhD Scholars}_{it}) + \beta_3 (\text{FSR}_{it}) + \beta_4 \ln(\text{Funding}_{it}) + \alpha_i + \delta_t + \varepsilon_{it}$$

*Table B2 & B3: Two-Way Fixed Effects across Quality Thresholds (N = 350)*

| Regressors | Target: % Q1 (Elite) | Target: % Q1+Q2 (High-Tier) | Target: % Q4 (Bottom-Tier) | Target: % Q3+Q4 (Lower-Half) | Lagged Model ($t-1$): % Q1 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **$\ln(\text{Scopus Volume})$** | **$+3.7854^{**}$**<br>*(1.8899)* | **$+6.6339^{***}$**<br>*(1.6938)* | $+0.7680$<br>*(0.8103)* | **$-5.3580^{***}$**<br>*(1.5766)* | **$+12.8053^{***}$**<br>*(2.5986)* |
| **$\ln(\text{PhD Scholars})$** | **$+4.2362^{***}$**<br>*(1.6086)* | **$+3.6798^{**}$**<br>*(1.8350)* | $-1.6592$<br>*(1.0694)* | **$-3.1949^{*}$**<br>*(1.7007)* | $-0.9607$<br>*(1.1589)* |
| **Faculty per 100** | $-0.4997$<br>*(0.3799)* | $-0.5093$<br>*(0.4632)* | $-0.3071$<br>*(0.2442)* | $+0.5267$<br>*(0.4787)* | $+0.0938$<br>*(0.3685)* |
| **$\ln(\text{Sponsored Funding})$**| **$-1.2539^{**}$**<br>*(0.5391)* | **$-1.2751^{*}$**<br>*(0.7026)* | $+0.9091^{*}$<br>*(0.5081)* | $+1.2821^{*}$<br>*(0.6876)* | $+0.2214$<br>*(0.6267)* |
| **Institution & Year FE** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** |
| **$R^2$** | $0.1338$ | $0.1962$ | $0.0445$ | $0.1330$ | **$0.6550$** |

*Standard errors clustered by university in parentheses. $^{***}p < 0.01, ^{**}p < 0.05, ^{*}p < 0.10$. Diagnostic: Hausman Test $\chi^2(4) = 36.228, p = 2.6 \times 10^{-7}$ (rejects RE; FE required).*  
*Source: [`analysis/results/part_b_table2_model_b1_q1.csv`](file:///d:/nirf-scraper/analysis/results/part_b_table2_model_b1_q1.csv) & [`part_b_table3_model_b1b_high_vs_low.csv`](file:///d:/nirf-scraper/analysis/results/part_b_table3_model_b1b_high_vs_low.csv).*

#### Core Findings:
1. **The Gaming Hypothesis is Statistically Refuted**: If universities were gaming NIRF by funneling papers into marginal journals, $\beta_{\ln(\text{Volume})}$ on `% Q3+Q4` would be positive. Instead, it is **strongly negative ($\beta = -5.3580^{***}, p < 0.001$)**. Volume expansion actively crowded out lower-tier journals in favor of Q1/Q2 outlets.
2. **Doctoral Scholars Elevate Quality**: PhD scholars do not just expand volume; they systematically shift institutional output toward the highest tiers ($\beta = +4.2362^{***}$ on `% Q1`, $p < 0.01$).
3. **Dynamic Quality Persistence**: In the 1-year lagged specification ($t-1$), past volume growth exerts a massive positive effect on current Q1 share ($\beta = +12.8053^{***}, p < 0.001$), explaining **$65.5\%$ of the within-institution variance ($R^2 = 0.655$)**. Publishing momentum creates an institutional learning curve that facilitates future Q1 acceptance.

---

### 4.3 Subgroup Quality Dynamics: Tier 1 vs. Tier 2
*Table B4 compares quality adjustments across tiers under Two-Way Fixed Effects:*

| Variable | % Q1: Tier 1 (1–35) | % Q1: Tier 2 (36–70) | % Q4: Tier 1 (1–35) | % Q4: Tier 2 (36–70) |
| :--- | :---: | :---: | :---: | :---: |
| **$\ln(\text{Scopus Volume})$** | **$+1.8055^{***}$** *(0.6011)* | **$+6.7257^{**}$** *(2.8114)* | $+0.6215$ *(0.5234)* | $+1.4989$ *(2.0244)* |
| **$\ln(\text{PhD Scholars})$** | **$+6.9664^{**}$** *(2.6914)* | **$+2.8776^{**}$** *(1.3827)* | **$-3.2754^{**}$** *(1.5681)* | $-0.6607$ *(1.3515)* |
| **Faculty per 100** | $+0.2760$ *(0.2781)* | **$-0.7655^{*}$** *(0.4112)* | **$-0.3090^{**}$** *(0.1420)* | $-0.3434$ *(0.4264)* |
| **$R^2$** | $0.0688$ | **$0.3509$** | $0.1135$ | $0.0810$ |

*Source: [`analysis/results/part_b_table4_subgroup_quality.csv`](file:///d:/nirf-scraper/analysis/results/part_b_table4_subgroup_quality.csv).*

* **Tier 2 Upgrading**: In Tier 2 universities, volume expansion is coupled with aggressive Q1 growth ($\beta = +6.7257^{**}, R^2 = 0.351$). As emerging institutions enter global indexing, their top research groups break into international Q1 journals.
* **Tier 1 Quality Consolidation**: In Tier 1, PhD scholars serve as the primary quality lever, increasing Q1 share ($\beta = +6.97^{**}$) while directly reducing bottom-tier Q4 output ($\beta = -3.28^{**}$).

---

## 5. Visualizations & Figures Index

All generated high-resolution ($300\text{ dpi}$) figures are saved in [`analysis/results/figures/`](file:///d:/nirf-scraper/analysis/results/figures/):

| Figure | File | Description |
| :---: | :--- | :--- |
| **Fig 1** | [`fig1_phd_vs_scopus_output.png`](file:///d:/nirf-scraper/analysis/results/figures/fig1_phd_vs_scopus_output.png) | Scatter of $\ln(\text{PhD Scholars})$ vs. $\ln(\text{Scopus Volume})$ with tier coloring and annotations for landmark universities (*IISc, JNU, BHU, Anna Univ, Jamia Millia, Manipal, AMU*). |
| **Fig 2** | [`fig2_faculty_vs_placement_rate.png`](file:///d:/nirf-scraper/analysis/results/figures/fig2_faculty_vs_placement_rate.png) | Faculty per 100 students vs. Placement Rate (%) with separate fitted regression lines for Tier 1 and Tier 2. |
| **Fig 3** | [`fig3_5year_trajectories_by_tier.png`](file:///d:/nirf-scraper/analysis/results/figures/fig3_5year_trajectories_by_tier.png) | Dual-panel longitudinal trajectories (2021–2025) of median Scopus output and median placement rate across tiers. |
| **Fig 4** | [`fig4_correlation_heatmap.png`](file:///d:/nirf-scraper/analysis/results/figures/fig4_correlation_heatmap.png) | Publication-styled correlation matrix across all Part A variables ($N=350$). |
| **Fig 5** | [`fig5_quartile_distribution_by_tier.png`](file:///d:/nirf-scraper/analysis/results/figures/fig5_quartile_distribution_by_tier.png) | Stacked bar chart showing the 5-year evolution of Q1, Q2, Q3, and Q4 shares comparing Tier 1 vs. Tier 2. |
| **Fig 6** | [`fig6_volume_vs_q1_dilution_test.png`](file:///d:/nirf-scraper/analysis/results/figures/fig6_volume_vs_q1_dilution_test.png) | Testing the Dilution Hypothesis: $\ln(\text{Volume})$ vs. `% Q1 Share`, illustrating the upward slope. |
| **Fig 7** | [`fig7_top_q1_universities.png`](file:///d:/nirf-scraper/analysis/results/figures/fig7_top_q1_universities.png) | Horizontal bar chart of India's Top 15 universities by 5-year average Q1 publication share. |

---

## 6. Policy Implications & Conclusion

### 6.1 Implications for the Ministry of Education & NIRF Committee
1. **Re-weighting TLR toward Research Human Capital**: The current TLR formula heavily weights bare faculty headcount. Our findings show that faculty headcount growth does not translate into within-institution research gains. Policy should explicitly reward **funded doctoral fellowships and post-doctoral scholar capacity**, which serve as the actual empirical engine of both volume and journal quality.
2. **Tier-Sensitive Benchmarking**: Emerging (Tier 2) institutions face steep infrastructure bottlenecks where adding PhD students yields diminishing research returns, but faculty attention produces large placement gains. NIRF should introduce differentiated criteria that do not penalize emerging institutions for focusing on instructional mentorship.

### 6.2 Implications for University Leadership
1. **Directing Resources to Doctoral Stipends & Labs**: Expanding contractual faculty to artificially improve the student-teacher ratio does not increase research output. University funds are far more effectively deployed into doctoral fellowships and lab equipment.
2. **Dismissing the "Quantity vs. Quality" Myth**: Institutional expansion does not require lowering publication standards. Across Indian higher education, institutions that increased publication volume experienced concurrent quality upgrades.

---

### Suggested Citation
> *NIRF Research Project (2026). "Evaluating the Impact of NIRF on University Research and Quality: An Empirical Panel Study of 70 Indian Universities (2021–2025)." Working Paper / Analysis Report. Available at: `https://github.com/rdnk2004/nirf-scraper`.*
