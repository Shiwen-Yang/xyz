#!/usr/bin/env python3
"""Generate the Stage A catalog from the existing section/field structure."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDANCE = {
    "EXECUTIVE.FACTS": "Summarize only the supplied accepted facts. Cover design, population, interventions, sample size, primary endpoints, and interim plans. Do not add assessments, concerns, conclusions, or new facts. Cite the original sources supplied with those facts.",
    "EXECUTIVE.ASSESSMENT": "Reviewer's assessment and conclusions; never request this from Elsa.",
    "BACKGROUND.SUBMISSION": "Describe the submission and current protocol identifier, version, and date as supplied.",
    "BACKGROUND.PRODUCT": "Summarize relevant sponsor-provided product background from the registered documents.",
    "BACKGROUND.HISTORY": "Summarize documented previous reviews, agreements, meetings, and regulatory events from supplied sources. Do not infer history from silence in the protocol.",
    "OBJECTIVES.PRIMARY": "Extract each primary objective verbatim. Exclude all secondary and exploratory objectives from this field.",
    "OBJECTIVES.OTHER": "Extract every secondary/key secondary objective verbatim, retaining sponsor priority labels. Do not select items by perceived statistical importance.",
    "DESIGN.POPULATION": "Summarize the target population and important eligibility boundaries, including age and disease status as stated.",
    "DESIGN.RANDOMIZATION": "Summarize the sponsor's treatment-assignment procedure, including randomized, concurrent-control, minimization, or single-arm design.",
    "DESIGN.ALLOCATION_RATIO": "Quote the allocation ratio and its named arms exactly. Do not infer a ratio from sample sizes.",
    "DESIGN.STRATA": "List stated randomization stratification factors and categories; distinguish these from analysis covariates.",
    "DESIGN.BLINDING": "State who is blinded and who can access allocation before database lock. Do not equate open label with an absence of blinded assessment.",
    "DESIGN.ARM.EXPERIMENTAL": "Summarize every experimental arm, including intervention, dose, route, and schedule where stated. Include the intervention in a single-arm study.",
    "DESIGN.ARM.CONTROL": "Summarize every control/comparator arm and its regimen where stated.",
    "DESIGN.SITES": "Summarize site counts and countries/regions, and US enrollment percentage if stated. Do not infer subject proportions from site counts.",
    "DESIGN.OTHER": "Summarize explicitly stated additional design features such as manufacturing delays or lot-consistency requirements. Do not evaluate adequacy or identify deficiencies.",
    "ENDPOINTS.PRIMARY": "Extract each primary endpoint's complete definition verbatim, including time windows, event/response definitions, and derivation rules wherever specified. Exclude secondary endpoints.",
    "ENDPOINTS.SECONDARY": "Extract all secondary/key secondary endpoint definitions verbatim, retaining sponsor priority labels. Do not omit endpoints because they seem less important.",
    "HYPOTHESIS.STATEMENT": "Quote formal hypotheses and parameter definitions for the named primary endpoint. Retain comparison direction and named arms. Do not construct a hypothesis if none is stated.",
    "HYPOTHESIS.MARGIN": "Quote applicable non-inferiority/equivalence margins and the sponsor's stated justification for the named primary endpoint. Do not evaluate the justification.",
    "HYPOTHESIS.SUCCESS": "Quote the sponsor's success criteria for the named primary endpoint and its role in overall study success, including joint requirements and testing order.",
    "INTERIM.PLAN": "Summarize whether interim efficacy, futility, safety analyses or sample-size re-estimation are explicitly planned. Distinguish absence of a plan from inability to locate it. Explicit no-interim statements are found facts.",
    "INTERIM.ADAPTIVE": "Summarize sponsor-described adaptive features; do not judge their appropriateness.",
    "INTERIM.LOOKS": "State the number and purpose of planned interim looks, distinguishing scheduled testing from other monitoring.",
    "INTERIM.METHOD": "Summarize the method specified for this named interim look, retaining cited method names/references as supplied.",
    "INTERIM.TIMING": "Summarize timing/information fraction, event counts, boundaries, alpha spending, and binding/nonbinding rules for this named look. Do not assess safety adequacy.",
    "INTERIM.OPERATING": "Summarize supplied stopping/continuation probabilities and their stated scenarios for this look; do not compute missing values.",
    "SAMPLE_SIZE.SUBJECTS": "State planned total and per-arm accrual and expected evaluable subjects, keeping endpoints/calculation scenarios explicit. Include medical/regulatory sizing reasons if stated.",
    "SAMPLE_SIZE.ALPHA": "State sponsor-reported sizing alpha and sidedness, with endpoint/scenario associations.",
    "SAMPLE_SIZE.POWER": "State sponsor-reported target or achieved power, with endpoint/scenario associations. Do not verify or compute power.",
    "SAMPLE_SIZE.EFFECT": "Summarize sponsor-assumed effect sizes and arm-specific values, naming each endpoint/scenario. Keep assumed true differences distinct from margins.",
    "SAMPLE_SIZE.SD": "State sponsor-assumed standard deviations for named continuous endpoints/scenarios.",
    "SAMPLE_SIZE.DROPOUT": "State sponsor-assumed dropout/missingness and how it enters each named sizing scenario.",
    "SAMPLE_SIZE.OTHER": "Summarize other stated sizing assumptions, including overdispersion, accrual and follow-up. Do not invent missing inputs.",
    "SAMPLE_SIZE.RATIONALE": "Summarize only the sponsor's supplied rationale/evidence for sizing assumptions. Do not supply a justification or evaluate adequacy.",
    "SAMPLE_SIZE.EVENTS": "State required event counts by endpoint/scenario and distinguish final from interim targets.",
    "SAMPLE_SIZE.VERIFICATION": "Independent reviewer verification; manual only. Elsa's sponsor-reported calculation cannot populate this field.",
    "OTHER.ISSUES": "Reviewer assessment of other important issues; manual only.",
    "TEAM.COMMENTS": "Reviewer-authored internal comments; manual only.",
    "SPONSOR.COMMENTS": "Reviewer-authored sponsor comments; manual only.",
}
for prefix in ("PRIMARY_ANALYSIS", "OTHER_ANALYSIS"):
    for suffix, instructions in {
        "METHOD": "Summarize the specified statistical method for this named endpoint, retaining named arms/comparisons and estimand details if supplied.",
        "COVARIATES": "List analysis covariates/strata for this named endpoint; distinguish them from randomization strata.",
        "SET": "Describe the sponsor's analysis-set membership and treatment-assignment rules for this endpoint, not just its acronym. Include any sponsor-supplied rationale; do not request or judge justification.",
        "MISSING": "Summarize missing-data and censoring rules/time points for this endpoint. Keep the main analysis distinct from sensitivity procedures.",
        "ALPHA": "State alpha, sidedness and sponsor-described multiplicity/gatekeeping procedures for this endpoint, including its relation to other endpoints and interim testing.",
        "SENSITIVITY": "Summarize sponsor-planned sensitivity/supportive methods, populations and missing-data approaches for this endpoint.",
        "SUBGROUP": "Summarize sponsor-planned subgroup analyses for this endpoint. Do not add subgroup requirements or reviewer recommendations.",
    }.items():
        GUIDANCE[prefix + "." + suffix] = instructions


def generate():
    sections = json.loads((ROOT / "review_template/sections.json").read_text())
    sections = copy.deepcopy(sections)
    verbatim = {"OBJECTIVES.PRIMARY", "OBJECTIVES.OTHER", "ENDPOINTS.PRIMARY", "ENDPOINTS.SECONDARY",
                "DESIGN.ALLOCATION_RATIO", "HYPOTHESIS.STATEMENT", "HYPOTHESIS.MARGIN", "HYPOTHESIS.SUCCESS"}
    manual = {"EXECUTIVE.ASSESSMENT", "SAMPLE_SIZE.VERIFICATION", "OTHER.ISSUES", "TEAM.COMMENTS", "SPONSOR.COMMENTS"}
    scopes = {"OBJECTIVES.PRIMARY": "primary_objective", "OBJECTIVES.OTHER": "secondary_objective",
              "ENDPOINTS.PRIMARY": "primary_endpoint", "ENDPOINTS.SECONDARY": "secondary_endpoint",
              "DESIGN.ARM.EXPERIMENTAL": "experimental_arm", "DESIGN.ARM.CONTROL": "control_arm",
              "INTERIM.METHOD": "interim_look", "INTERIM.TIMING": "interim_look", "INTERIM.OPERATING": "interim_look"}
    discovery = set(scopes) - {"INTERIM.TIMING", "INTERIM.OPERATING"}
    for section in sections:
        section.pop("instructions")
        if section["number"] == 1:
            section["fields"] = [dict(id="EXECUTIVE.FACTS", label="Factual summary", depth=0, group=False),
                                 dict(id="EXECUTIVE.ASSESSMENT", label="Reviewer assessment", depth=0, group=False)]
        if section["number"] == 9:
            section["fields"].insert(0, dict(id="INTERIM.PLAN", label="Interim analysis plan", depth=0, group=False))
        for field in section["fields"]:
            identifier = field["id"]
            if identifier == "OBJECTIVES.OTHER":
                field["label"] = "Secondary objectives"
            field["mode"] = "group" if field["group"] else ("manual" if identifier in manual else "verbatim" if identifier in verbatim else "summary")
            field["scope"] = scopes.get(identifier, "primary_endpoint" if identifier.startswith(("PRIMARY_ANALYSIS.", "HYPOTHESIS.")) else "secondary_endpoint" if identifier.startswith("OTHER_ANALYSIS.") else "study")
            field["discovers_entities"] = identifier in discovery
            field["source_scope"] = "supplied_documents" if identifier.startswith("BACKGROUND.") else "protocol"
            field["instructions"] = "Structural label; not an extraction field." if field["group"] else GUIDANCE[identifier]
    output = ROOT / "review_template/stage_a/catalog.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dict(catalog_version=1, sections=sections), ensure_ascii=False, indent=2) + "\n")
    lines = ["# Stage A field catalog", "", "Generated from the existing template structure. Edit scripts/make_stage_a_catalog.py to change extraction rules, then regenerate. Existing workspaces retain their catalog snapshot.", "",
             "Verbatim text is preserved in provenance. You may accept edited report wording without replacing the original quotation. Every source-backed field still requires reviewer verification. All secondary objectives and endpoints are collected; inclusion in the memo is a separate decision.", ""]
    for section in sections:
        lines.extend(["## " + section["title"], "", "| Field | Mode | Instance scope | Retrieval instruction |", "| --- | --- | --- | --- |"])
        for field in section["fields"]:
            if field["mode"] != "group":
                lines.append(f"| {field['id']} | {field['mode']} | {field['scope']} | {field['instructions']} |")
        lines.append("")
    (output.parent / "FIELD_CATALOG.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    generate()
