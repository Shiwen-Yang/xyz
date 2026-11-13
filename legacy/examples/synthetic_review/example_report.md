---
{"title": "DRAFT — Statistical Review and Evaluation for Pre-Licensure Submissions", "author": "SYNTHETIC EXAMPLE — OBPV/DB", "date": "2026-01-20", "submission": "SYN-001 — entirely fictional; unverified sizing assumptions", "subtitle": "SYN-001 — entirely fictional; unverified sizing assumptions"}
---

# Executive Summary:

This fictional phase 2, randomized, double-blind study assigns 300 adults with imaginary condition Q to low-dose Product A, high-dose Product A, or placebo. The co-primary endpoints are week-12 change in Q score and Q response. No interim analyses are planned. A reviewer-approved request asks for the sizing basis for RESPONSE and the joint success criterion. Independent verification of the reported SCORE sizing remains pending.

# Background:

Protocol SYN-001, version 1.0 dated January 15, 2026, proposes a phase 2 study.

Fictional Product A is an investigational synthetic product for imaginary condition Q.

Prior regulatory history and agreements were not supplied; reviewer input is required.

# Primary Objective(s):

Compare each active dose with placebo on change in Q score and Q response at week 12. Both endpoints must succeed for a dose to be declared successful.

Compare change in Q score at week 24 as an exploratory secondary objective.

# Design Features:

- **Study population:** Adults aged 18–65 with imaginary condition Q.

- **Treatment Allocation and Randomization:** Randomized 1:1:1 with region stratification.

    - **allocation ratio:** 1:1:1 (low dose:high dose:placebo).

    - **stratification factors:** Region (North/South).

- **Blinding:** Subjects, investigators, and outcome assessors are blinded; the dispensing pharmacist has allocation access before database lock.

**Treatment Arms:**

| Arm | Regimen | Randomized subjects |
| --- | --- | --- |
| Low-dose Product A | 1 unit orally daily for 12 weeks | 100 |
| High-dose Product A | 2 units orally daily for 12 weeks | 100 |
| Placebo | Matching placebo daily for 12 weeks | 100 |

- **Site(s):** 12 sites: 8 in the US and 4 in Canada. Expected US enrollment percentage is not specified.

# Endpoints:

- **Primary:** SCORE: week-12 Q score minus baseline Q score; higher scores are better. RESPONSE: an increase of at least 5 Q-score points from baseline at week 12.

- **Secondary:** Baseline-to-week-24 change in Q score.

# Statistical Hypothesis:

For each active dose versus placebo: SCORE, $H_0: \mu_A-\mu_P=0$ versus $H_1: \mu_A-\mu_P\ne0$, where $\mu$ is mean change in Q score; RESPONSE, $H_0: p_A-p_P=0$ versus $H_1: p_A-p_P\ne0$, where $p$ is response probability. A denotes the active dose and P placebo.


For a dose to succeed, both co-primary endpoint comparisons must be significant. Four comparisons (two doses by two endpoints) each use two-sided $\alpha=0.0125$, Bonferroni allocation from family $\alpha=0.05$.

# Analyses for Primary Endpoint(s):

## Endpoint: SCORE

- **Primary analysis:**

    - **statistical method:** ANCOVA.

    - **covariates or strata:** Treatment, region, and baseline Q score.

    - **analysis set:** All randomized subjects, analyzed as randomized (ITT).

    - **missing data handling:** Multiply impute week-12 Q scores under missing at random using treatment, region, and baseline Q score.

    - **α-level:** Two-sided 0.0125 per dose comparison, Bonferroni allocation from family alpha 0.05 across four comparisons.

- **Sensitivity/supportive:** Pattern-mixture model.

- **Subgroup analysis:** Exploratory age (18–40/>40), sex, and race subgroups.

## Endpoint: RESPONSE

- **Primary analysis:**

    - **statistical method:** Region-stratified CMH test.

    - **covariates or strata:** Region.

    - **analysis set:** All randomized subjects, analyzed as randomized (ITT).

    - **missing data handling:** Derive response from each multiply imputed week-12 Q score.

    - **α-level:** Two-sided 0.0125 per dose comparison, Bonferroni allocation from family alpha 0.05 across four comparisons.

- **Sensitivity/supportive:** Missing response treated as nonresponse.

- **Subgroup analysis:** Exploratory age (18–40/>40), sex, and race subgroups.

# Analyses for Other Important Endpoint(s):

- **Primary analysis:**

    - **statistical method:** ANCOVA for week-24 change in Q score.

    - **covariates or strata:** Treatment, region, and baseline Q score.

    - **analysis set:** All randomized subjects, analyzed as randomized (ITT).

    - **missing data handling:** Multiple imputation under missing at random.

    - **α-level:** Exploratory; no confirmatory alpha allocation.

- **Sensitivity/supportive:** Observed-case ANCOVA.

- **Subgroup analysis:** Exploratory age (18–40/>40), sex, and race subgroups.

# Interim Analyses:

None.

# Sample Size Estimation:

- **Number of subjects to be accrued/evaluated:** 300 randomized subjects (100 per arm); approximately 270 expected to contribute week-12 measurements.

- **Type-I error rate (one or two-sided):** Two-sided 0.0125 for the reported SCORE sizing calculation.

- **Power:** Sponsor-reported 80% for SCORE; no RESPONSE power calculation is provided.

- **Assumed values in the estimation:**

    - **Treatment effect size:** 4-point mean difference for SCORE.

    - **Standard deviation:** 10 for SCORE.

    - **Dropout/missing rate:** 10% missingness.


- **Rationale provided for assumed values:** An internal planning exercise is cited without details.


- **Calculation verification:** Pending reviewer verification. Sponsor-reported figures have not been independently reproduced.

# Other Aspects:

No additional issue identified by the fictional reviewer in the supplied synthetic materials.

# Comments to CBER Review Team:

The response-endpoint sizing question remains open. The SCORE calculation has not yet been independently reproduced.

# Comments and Questions to Sponsor:

1. Please provide the sample-size/power basis for the co-primary RESPONSE endpoint and explain how the planned sample size supports the joint endpoint success criterion for each dose.
