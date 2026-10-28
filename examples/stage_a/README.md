# Fictional Stage A pilot

This example exercises **local preparation, import, field verification and report assembly**. The JSON fixture is simulated; it is not an Elsa test result and is not a scientific recommendation. Its source documents are the fictional Markdown protocol/background in `../synthetic_review/`. Page references are null because these are text sources.

Run from the repository root:

```sh
python3 scripts/demo_stage_a.py reviews/stage-a-demo
```

The command creates a new Stage A workspace, copies/registers those sources, prepares sections 3/4/5, inserts the new request ID into a copy of `elsa_pilot_response.json`, imports it, and generates the verification report. It refuses an existing destination and approves nothing. The response fixture's placeholder request ID deliberately cannot be imported into an unrelated live request unchanged.

Open `reviews/stage-a-demo/stage_a/verification.md`. Inspect the objective, endpoint, and arm records, follow a text-file link, and edit the proposed report wording. Record a decision using a real candidate ID from the report:

```sh
python3 scripts/review.py review reviews/stage-a-demo --candidate c_REPLACE_WITH_ACTUAL_ID --accept --reviewer "Test reviewer"
python3 scripts/review.py build reviews/stage-a-demo --output output/stage-a-demo.md
```

Only accepted text appears in the draft. Remaining fields are placeholders. The original quote/export remains available after edits. Reimport `simulated_elsa_response.json` to see a new proposal beside the accepted value without overwriting it. To exercise Word too, build to `output/stage-a-demo.docx` with Pandoc available and inspect every page.

Expected source facts:

| Item | Expected result |
| --- | --- |
| Objectives | Primary and secondary objectives remain in distinct fields |
| Combined primary wording | Two objective records retain the same combined sponsor sentence, with an explicit explanation; check this grouping manually |
| Primary endpoints | SCORE change at week 12 and RESPONSE (increase of at least 5 points at week 12) |
| Secondary endpoint | Change in Q score at week 24 |
| Arms | Low-dose Product A, high-dose Product A, matching placebo |
| Allocation | 1:1:1 |
| Blinding exception | Dispensing pharmacist has allocation access before database lock |
| Sites | 8 US, 4 Canada; subject percentage cannot be inferred from those counts |

For an actual Elsa pilot, initialize a separate workspace and register the fictional sources. Upload that workspace's generated instructions and the source files to Elsa; import Elsa's downloaded response. Do not upload this fixture or the completed legacy report as evidence. If you export the source text as a searchable PDF, register that PDF, remove/update the text-only page-unavailability statement in your test copy, and verify actual page references.

This small source does not establish performance on lengthy protocols, scanned content, complicated tables, multiple amendments, or Elsa context limits. Stage A's validators cannot detect every semantic error, including secondary text incorrectly placed inside a primary-objective string; source verification is essential.
