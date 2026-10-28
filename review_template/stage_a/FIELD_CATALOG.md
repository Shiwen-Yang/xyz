# Stage A field catalog

Generated from the existing template structure. Edit scripts/make_stage_a_catalog.py to change extraction rules, then regenerate. Existing workspaces retain their catalog snapshot.

Verbatim text is preserved in provenance. You may accept edited report wording without replacing the original quotation. Every source-backed field still requires reviewer verification. All secondary objectives and endpoints are collected; inclusion in the memo is a separate decision.

## Executive Summary:

| Field | Mode | Instance scope | Retrieval instruction |
| --- | --- | --- | --- |
| EXECUTIVE.FACTS | summary | study | Summarize only the supplied accepted facts. Cover design, population, interventions, sample size, primary endpoints, and interim plans. Do not add assessments, concerns, conclusions, or new facts. Cite the original sources supplied with those facts. |
| EXECUTIVE.ASSESSMENT | manual | study | Reviewer's assessment and conclusions; never request this from Elsa. |

## Background:

| Field | Mode | Instance scope | Retrieval instruction |
| --- | --- | --- | --- |
| BACKGROUND.SUBMISSION | summary | study | Describe the submission and current protocol identifier, version, and date as supplied. |
| BACKGROUND.PRODUCT | summary | study | Summarize relevant sponsor-provided product background from the registered documents. |
| BACKGROUND.HISTORY | summary | study | Summarize documented previous reviews, agreements, meetings, and regulatory events from supplied sources. Do not infer history from silence in the protocol. |

## Primary Objective(s):

| Field | Mode | Instance scope | Retrieval instruction |
| --- | --- | --- | --- |
| OBJECTIVES.PRIMARY | verbatim | primary_objective | Extract each primary objective verbatim. Exclude all secondary and exploratory objectives from this field. |
| OBJECTIVES.OTHER | verbatim | secondary_objective | Extract every secondary/key secondary objective verbatim, retaining sponsor priority labels. Do not select items by perceived statistical importance. |

## Design Features:

| Field | Mode | Instance scope | Retrieval instruction |
| --- | --- | --- | --- |
| DESIGN.POPULATION | summary | study | Summarize the target population and important eligibility boundaries, including age and disease status as stated. |
| DESIGN.RANDOMIZATION | summary | study | Summarize the sponsor's treatment-assignment procedure, including randomized, concurrent-control, minimization, or single-arm design. |
| DESIGN.ALLOCATION_RATIO | verbatim | study | Quote the allocation ratio and its named arms exactly. Do not infer a ratio from sample sizes. |
| DESIGN.STRATA | summary | study | List stated randomization stratification factors and categories; distinguish these from analysis covariates. |
| DESIGN.BLINDING | summary | study | State who is blinded and who can access allocation before database lock. Do not equate open label with an absence of blinded assessment. |
| DESIGN.ARM.EXPERIMENTAL | summary | experimental_arm | Summarize every experimental arm, including intervention, dose, route, and schedule where stated. Include the intervention in a single-arm study. |
| DESIGN.ARM.CONTROL | summary | control_arm | Summarize every control/comparator arm and its regimen where stated. |
| DESIGN.SITES | summary | study | Summarize site counts and countries/regions, and US enrollment percentage if stated. Do not infer subject proportions from site counts. |
| DESIGN.OTHER | summary | study | Summarize explicitly stated additional design features such as manufacturing delays or lot-consistency requirements. Do not evaluate adequacy or identify deficiencies. |

## Endpoints:

| Field | Mode | Instance scope | Retrieval instruction |
| --- | --- | --- | --- |
| ENDPOINTS.PRIMARY | verbatim | primary_endpoint | Extract each primary endpoint's complete definition verbatim, including time windows, event/response definitions, and derivation rules wherever specified. Exclude secondary endpoints. |
| ENDPOINTS.SECONDARY | verbatim | secondary_endpoint | Extract all secondary/key secondary endpoint definitions verbatim, retaining sponsor priority labels. Do not omit endpoints because they seem less important. |

## Statistical Hypothesis:

| Field | Mode | Instance scope | Retrieval instruction |
| --- | --- | --- | --- |
| HYPOTHESIS.STATEMENT | verbatim | primary_endpoint | Quote formal hypotheses and parameter definitions for the named primary endpoint. Retain comparison direction and named arms. Do not construct a hypothesis if none is stated. |
| HYPOTHESIS.MARGIN | verbatim | primary_endpoint | Quote applicable non-inferiority/equivalence margins and the sponsor's stated justification for the named primary endpoint. Do not evaluate the justification. |
| HYPOTHESIS.SUCCESS | verbatim | primary_endpoint | Quote the sponsor's success criteria for the named primary endpoint and its role in overall study success, including joint requirements and testing order. |

## Analyses for Primary Endpoint(s):

| Field | Mode | Instance scope | Retrieval instruction |
| --- | --- | --- | --- |
| PRIMARY_ANALYSIS.METHOD | summary | primary_endpoint | Summarize the specified statistical method for this named endpoint, retaining named arms/comparisons and estimand details if supplied. |
| PRIMARY_ANALYSIS.COVARIATES | summary | primary_endpoint | List analysis covariates/strata for this named endpoint; distinguish them from randomization strata. |
| PRIMARY_ANALYSIS.SET | summary | primary_endpoint | Describe the sponsor's analysis-set membership and treatment-assignment rules for this endpoint, not just its acronym. Include any sponsor-supplied rationale; do not request or judge justification. |
| PRIMARY_ANALYSIS.MISSING | summary | primary_endpoint | Summarize missing-data and censoring rules/time points for this endpoint. Keep the main analysis distinct from sensitivity procedures. |
| PRIMARY_ANALYSIS.ALPHA | summary | primary_endpoint | State alpha, sidedness and sponsor-described multiplicity/gatekeeping procedures for this endpoint, including its relation to other endpoints and interim testing. |
| PRIMARY_ANALYSIS.SENSITIVITY | summary | primary_endpoint | Summarize sponsor-planned sensitivity/supportive methods, populations and missing-data approaches for this endpoint. |
| PRIMARY_ANALYSIS.SUBGROUP | summary | primary_endpoint | Summarize sponsor-planned subgroup analyses for this endpoint. Do not add subgroup requirements or reviewer recommendations. |

## Analyses for Other Important Endpoint(s):

| Field | Mode | Instance scope | Retrieval instruction |
| --- | --- | --- | --- |
| OTHER_ANALYSIS.METHOD | summary | secondary_endpoint | Summarize the specified statistical method for this named endpoint, retaining named arms/comparisons and estimand details if supplied. |
| OTHER_ANALYSIS.COVARIATES | summary | secondary_endpoint | List analysis covariates/strata for this named endpoint; distinguish them from randomization strata. |
| OTHER_ANALYSIS.SET | summary | secondary_endpoint | Describe the sponsor's analysis-set membership and treatment-assignment rules for this endpoint, not just its acronym. Include any sponsor-supplied rationale; do not request or judge justification. |
| OTHER_ANALYSIS.MISSING | summary | secondary_endpoint | Summarize missing-data and censoring rules/time points for this endpoint. Keep the main analysis distinct from sensitivity procedures. |
| OTHER_ANALYSIS.ALPHA | summary | secondary_endpoint | State alpha, sidedness and sponsor-described multiplicity/gatekeeping procedures for this endpoint, including its relation to other endpoints and interim testing. |
| OTHER_ANALYSIS.SENSITIVITY | summary | secondary_endpoint | Summarize sponsor-planned sensitivity/supportive methods, populations and missing-data approaches for this endpoint. |
| OTHER_ANALYSIS.SUBGROUP | summary | secondary_endpoint | Summarize sponsor-planned subgroup analyses for this endpoint. Do not add subgroup requirements or reviewer recommendations. |

## Interim Analyses:

| Field | Mode | Instance scope | Retrieval instruction |
| --- | --- | --- | --- |
| INTERIM.PLAN | summary | study | Summarize whether interim efficacy, futility, safety analyses or sample-size re-estimation are explicitly planned. Distinguish absence of a plan from inability to locate it. Explicit no-interim statements are found facts. |
| INTERIM.ADAPTIVE | summary | study | Summarize sponsor-described adaptive features; do not judge their appropriateness. |
| INTERIM.LOOKS | summary | study | State the number and purpose of planned interim looks, distinguishing scheduled testing from other monitoring. |
| INTERIM.METHOD | summary | interim_look | Summarize the method specified for this named interim look, retaining cited method names/references as supplied. |
| INTERIM.TIMING | summary | interim_look | Summarize timing/information fraction, event counts, boundaries, alpha spending, and binding/nonbinding rules for this named look. Do not assess safety adequacy. |
| INTERIM.OPERATING | summary | interim_look | Summarize supplied stopping/continuation probabilities and their stated scenarios for this look; do not compute missing values. |

## Sample Size Estimation:

| Field | Mode | Instance scope | Retrieval instruction |
| --- | --- | --- | --- |
| SAMPLE_SIZE.SUBJECTS | summary | study | State planned total and per-arm accrual and expected evaluable subjects, keeping endpoints/calculation scenarios explicit. Include medical/regulatory sizing reasons if stated. |
| SAMPLE_SIZE.ALPHA | summary | study | State sponsor-reported sizing alpha and sidedness, with endpoint/scenario associations. |
| SAMPLE_SIZE.POWER | summary | study | State sponsor-reported target or achieved power, with endpoint/scenario associations. Do not verify or compute power. |
| SAMPLE_SIZE.EFFECT | summary | study | Summarize sponsor-assumed effect sizes and arm-specific values, naming each endpoint/scenario. Keep assumed true differences distinct from margins. |
| SAMPLE_SIZE.SD | summary | study | State sponsor-assumed standard deviations for named continuous endpoints/scenarios. |
| SAMPLE_SIZE.DROPOUT | summary | study | State sponsor-assumed dropout/missingness and how it enters each named sizing scenario. |
| SAMPLE_SIZE.OTHER | summary | study | Summarize other stated sizing assumptions, including overdispersion, accrual and follow-up. Do not invent missing inputs. |
| SAMPLE_SIZE.RATIONALE | summary | study | Summarize only the sponsor's supplied rationale/evidence for sizing assumptions. Do not supply a justification or evaluate adequacy. |
| SAMPLE_SIZE.EVENTS | summary | study | State required event counts by endpoint/scenario and distinguish final from interim targets. |
| SAMPLE_SIZE.VERIFICATION | manual | study | Independent reviewer verification; manual only. Elsa's sponsor-reported calculation cannot populate this field. |

## Other Aspects:

| Field | Mode | Instance scope | Retrieval instruction |
| --- | --- | --- | --- |
| OTHER.ISSUES | manual | study | Reviewer assessment of other important issues; manual only. |

## Comments to CBER Review Team:

| Field | Mode | Instance scope | Retrieval instruction |
| --- | --- | --- | --- |
| TEAM.COMMENTS | manual | study | Reviewer-authored internal comments; manual only. |

## Comments and Questions to Sponsor:

| Field | Mode | Instance scope | Retrieval instruction |
| --- | --- | --- | --- |
| SPONSOR.COMMENTS | manual | study | Reviewer-authored sponsor comments; manual only. |

