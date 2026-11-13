# Stage A walkthrough

Stage A retrieves sponsor facts and assembles the memo. It does not identify deficiencies, evaluate methods, independently verify calculations, or write reviewer conclusions. Work from the repository root, using the `.venv` Python (`.venv/bin/python`) or any Python 3.10+ for the CLI, which needs no extra packages.

For routine use without terminal commands, start with the [guided local UI](STREAMLIT_UI.md). This page remains the command-line reference and explains the underlying artifacts in more detail.

## 1. Create a workspace and register sources

```sh
python3 scripts/review.py init reviews/my-review
python3 scripts/review.py source reviews/my-review reviews/my-review/protocol.pdf --id PROTOCOL --role protocol --version "1.0" --date "2026-01-15" --pages 120
```

Place the PDF at the supplied path first; initialization does not provide a protocol. Registration records its filename, role, version/date, optional PDF page count, local path, and SHA-256 fingerprint. It does not extract text. Register background files with distinct IDs and `--role background`. Use `unknown` explicitly when a date/version is unavailable.

Keep registered files available. To move one, register its new path under the same ID and metadata. Replacing its content/version makes previous results stale. Each request must include exactly one current protocol; use `--sources` to choose a subset when multiple versions are registered.

Fill title/author/date/submission in `review.json`; a blank report date is allowed. `stage_a/` contains the frozen catalog, requests, provenance, edits, and decisions. Do not hand-edit its JSON state or import archives. Use one CLI process at a time per workspace. Submissions and working files belong under Git-ignored `reviews/`, reports under `output/`.

## 2. Prepare and import a small batch

```sh
python3 scripts/review.py prepare reviews/my-review --sections 3,4,5
```

Upload the printed request folder's **instructions.md** and the listed source documents to Elsa. The instructions embed the field requirements, source register, request identity, and strict JSON Schema. Paste them if Markdown upload is unavailable. A filename in the manifest does not attach the PDF; attach each relevant document manually.

Download Elsa's response as UTF-8 JSON, then:

```sh
python3 scripts/review.py import reviews/my-review reviews/my-review/elsa-response.json
python3 scripts/review.py review reviews/my-review
```

Invalid exports are rejected before import state changes. Valid exports are preserved byte-for-byte and staged as candidates. No result is accepted or substituted into the report automatically. Retries must match the request ID and include every field in that request. Prepare a smaller fresh request to retry selected fields, or reimport a complete response for the unchanged request.

More selection options:

```sh
python3 scripts/review.py prepare reviews/my-review --fields DESIGN.POPULATION,DESIGN.BLINDING
python3 scripts/review.py prepare reviews/my-review --sections 2 --sources PROTOCOL,BACKGROUND_01
```

Sources default to all registered documents. `--sections all` requests factual retrieval fields in sections 2–10, excluding the later executive summary. Smaller batches are recommended until Elsa's practical limits are understood. Manual fields and structural labels are never requested.

## 3. Inspect, edit, and decide fields

Open `stage_a/verification.md`. Each candidate shows Elsa's original proposed text, source excerpts and locations, search limits, the current accepted text, and a linked editable `.txt` file.

1. Check passages and page/section references against the source.
2. Edit the linked text file if necessary. This is plain report text, not a Markdown layout file. The original quotation and export remain preserved.
3. Explicitly decide using the actual candidate ID shown in the report:

```sh
python3 scripts/review.py review reviews/my-review --candidate c_REPLACE_WITH_ACTUAL_ID --accept --reviewer "Your name"
python3 scripts/review.py review reviews/my-review --candidate c_REPLACE_WITH_ACTUAL_ID --reject --reviewer "Your name" --reason "Wrong endpoint definition"
```

Add `--exclude --reason "..."` to acceptance to keep a reviewed record but omit it from the memo. Non-found dispositions require a reason. Accepted `not_applicable` results are omitted automatically. Rejecting a proposal neither invents a replacement nor removes earlier accepted wording; use corrected content or an explicit exclusion/disposition to resolve it.

All secondary objectives/endpoints are extracted. Inclusion is field-by-field: if you exclude an endpoint definition, review the inclusion of its related analyses/hypotheses too. Inclusion decisions do not cascade automatically.

Editing text after acceptance creates an unapproved change. Accept again to adopt it. Later imports get separate editable files and are shown beside prior accepted wording. Importing or regenerating does not overwrite your edits. Decision history preserves who accepted which text and when.

## 4. Complete retrieval and draft the factual summary

After accepting endpoint definitions, request their associated hypotheses/analyses:

```sh
python3 scripts/review.py prepare reviews/my-review --sections 6,7,8
python3 scripts/review.py prepare reviews/my-review --sections 2,9,10
```

Import and review each response. Requests reuse accepted endpoint IDs. Methods, populations, missing-data rules, hypotheses, and alpha remain attached to each named endpoint. Arms and interim looks have distinct identities too.

If an inventory is absent or undiscoverable, Elsa must return one explicit non-found record with instance_id `none`, not an empty array or fabricated entity. An explicit no-interim statement is a found plan; individual look fields can have evidence-backed inapplicable dispositions.

Once factual fields are reviewed, prepare the factual executive summary separately:

```sh
python3 scripts/review.py prepare reviews/my-review --fields EXECUTIVE.FACTS
```

Its request includes accepted factual wordings and original evidence. Import/review this new draft. New summary evidence outside those references is rejected. Changes to accepted facts or source versions make the summary stale and require a fresh summary request. The manual assessment portion remains separate.

## 5. Write the manual fields

Editable files in `stage_a/manual/` cover executive assessment, independent calculation verification, other aspects, review-team comments, and sponsor comments. Write each field, then acknowledge it:

```sh
python3 scripts/review.py review reviews/my-review --manual SAMPLE_SIZE.VERIFICATION --accept --reviewer "Your name"
```

For calculation verification, record actual results/procedure or an explicit pending/not-performed disposition. Sponsor-reported calculations do not constitute independent verification. A manual field can be excluded with a reason after supplying its disposition. `reviewer_checks.md` remains your scientific/source and layout checklist; Stage A never asks Elsa for deficiency identification.

## 6. Build and inspect the memo

```sh
python3 scripts/review.py build reviews/my-review --output output/my-review-draft.docx
python3 scripts/review.py build reviews/my-review --output output/my-review-draft.md
python3 scripts/review.py build reviews/my-review --output output/my-review-final.docx --final --reviewer-approved
```

Pandoc is needed only for `.docx`. Pass `--pandoc /path/to/pandoc` if it is not on PATH. The build saves assembled Markdown and a check log alongside Word. Drafts show placeholders for unverified fields; unreviewed candidate text never appears.

Stage A renders the 13 sections from reviewed snapshots and fixed templates. Evidence and review logs remain separate. **Do not edit `sections/*.md` for Stage A:** those are legacy files, not the source of the new memo. Edit individual field text and accept it instead.

Final builds require reviewed field dispositions, manual fields, current sources, intact import archives, and a current executive summary. `--reviewer-approved` and `--acknowledge-unresolved` cannot bypass field verification. Explicitly accepted uncertain results may remain, with their dispositions your responsibility. Scientific accuracy is not established by a final flag. Open Word and check every page.

Values are escaped as plain text: imported markup cannot create headings, images, links, raw TeX, or tables. Lists and named endpoint subsections are generated locally. Source formulas remain text; Stage A does not infer TeX or reconstruct PDF equation objects. Add advanced equations, schematics, or custom tables in a separate final Word copy if necessary. Regenerating does not preserve edits made inside Word. Existing legacy formatting examples remain available in `examples/synthetic_review/`.

## Contract and limits

- See [the full field catalog](../review_template/stage_a/FIELD_CATALOG.md). Verbatim, summary, manual and group modes are explicit.
- Each request exports a JSON Schema. Local validation implements exactly the vocabulary generated by the fixed v1 contract, plus coverage, identity, evidence and verbatim/excerpt consistency rules.
- Extraction statuses are `found`, `not_found`, `not_applicable`, `conflicting`, and `unreadable`; reviewer decisions are separate.
- Source references separate 1-based PDF position, printed page label, and section. Unavailable locations are null. A known registered page count bounds allowed page references.
- Verbatim values must match their returned excerpts, ignoring whitespace only. The importer cannot prove those excerpts exist in the PDF or detect all semantic leakage. Verify them manually.
- Elsa context/file limits, long-protocol accuracy, and real-world retrieval completeness are not established by software tests. Custom agents/libraries are not required.
- Raw exports, candidates and accepted values are separate. Source hashes and archive integrity checks detect changed local inputs. Do not manually edit the state/archives to resolve warnings.

## Maintenance and compatibility

The original section-based workflow, its templates, and the original TeX memo are archived under `legacy/`; see [legacy/README.md](../legacy/README.md). `scripts/review.py` handles Stage A workspaces only, so evaluative legacy prompts cannot be mixed in accidentally. Workspaces without `workflow: "stage-a"` are not opened by the CLI or UI.

Regenerate the Stage A catalog/field guide with `python3 scripts/make_stage_a_catalog.py` after updating its explicit retrieval-only rules or the underlying section structure (`review_template/sections.json`). Existing workspaces retain their catalog snapshot; there is no automatic migration.

Run `python3 -m unittest discover -s tests -v`. Set environment variable `PANDOC` to a binary path for Word integration tests if necessary; otherwise those cases skip. These tests do not call Elsa or measure its retrieval accuracy. Generated Word structure is checked, but visual layout needs manual Word inspection or a LibreOffice rendering environment.
