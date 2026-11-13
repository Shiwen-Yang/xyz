# Instructions: Sample Size Estimation:

Original source: `legacy/tex/content/10_sample_size_estimation.tex`.

List planned accrual and expected primary-analysis contributors. If sizing is based on medical/regulatory considerations instead of power, explain that basis in the first bullet and omit the remaining calculation bullets; preserve any reviewer assessment of safety-sizing parameters in that explanation. Keep sponsor calculations separate from independent reviewer verification.

## SAMPLE_SIZE.SUBJECTS — Number of subjects to be accrued/evaluated

Give total and per-arm planned accrual, and expected evaluable subjects. Describe medical/regulatory sizing reasons if applicable.

## SAMPLE_SIZE.ALPHA — Type-I error rate (one or two-sided)

State the alpha and sidedness used in sizing, e.g. one-sided 0.025 or two-sided 0.05.

## SAMPLE_SIZE.POWER — Power

State target power or the reported power achieved with the planned sample size.

## SAMPLE_SIZE.ASSUMPTIONS — Assumed values in the estimation

Group of sizing assumptions; omit individual assumptions that do not apply.

## SAMPLE_SIZE.EFFECT — Treatment effect size

Describe the expected/desired/clinically meaningful effect, with arm-specific rates where applicable; examples include HR 0.60 with medians or a rate difference of 0.30 (0.10 vs 0.40). For NI/equivalence, retain the assumed true difference, possibly zero, separately from the margin.

## SAMPLE_SIZE.SD — Standard deviation

Give the assumed SD for a continuous outcome; omit otherwise.

## SAMPLE_SIZE.DROPOUT — Dropout/missing rate

Give the assumed dropout/missing-data rate and its role in sizing.

## SAMPLE_SIZE.OTHER — Others

Include relevant assumptions such as overdispersion, accrual rates, and follow-up; omit if not applicable.

## SAMPLE_SIZE.RATIONALE — Rationale provided for assumed values

Describe the sponsor rationale or cited evidence for sizing assumptions; missing rationale is a gap, not an invitation to create one.

## SAMPLE_SIZE.EVENTS — Number of events required to stop/complete the trial

State required events for a time-to-event design and distinguish interim from final targets. Omit if not applicable.

## SAMPLE_SIZE.VERIFICATION — Calculation verification

Default to Pending reviewer verification. A protocol calculation is sponsor-reported, not independently verified. Only use Yes/No after the reviewer supplies verification results, software/procedure/version and inputs, and an accepted discrepancy assessment. A small difference may be accepted by the reviewer; the chatbot cannot decide that tolerance. If No, draft a potential sponsor comment for approval. Describe safety-sizing justification where relevant. Do not claim that an independent calculation occurred unless its results are supplied.
