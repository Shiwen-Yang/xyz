# Legacy Markdown review workflow

Prepare a statistical-review memo with an approved work chatbot, then assemble an editable Word report locally. The Markdown templates preserve the 13 sections in `review_report.tex`; the existing TeX and PDF remain unchanged.

This guide describes the original section-editing workflow. Existing workspaces remain unchanged. New JSON-based Elsa reviews use Stage A, documented in the repository README. Run all commands below from the repository root.

## Start here

You need **Python 3.9+** and **Pandoc** on the computer that builds Word files. Python uses only its standard library: no pip packages, API keys, agent framework, or cloud service is needed. Install Pandoc using your organization's approved process ([official installation instructions](https://pandoc.org/installing.html)). The scripts make no network requests. Use `python` instead of `python3` if that is your Windows Python command.

From this repository's folder:

```sh
python3 scripts/review.py init reviews/my-review --workflow legacy
```

This creates a local working folder with `sections/`, `documents.md`, `evidence.md`, `issues.md`, `reviewer_checks.md`, and `review.json`. It refuses to overwrite an existing folder. `reviews/` and `output/` are Git-ignored so submissions and working reports placed there are not added accidentally; do not put proprietary inputs in the reusable template or synthetic example folders.

1. Fill in `reviews/my-review/documents.md`: identify the current main protocol and each background source by version/date and role. Fill the report title/author/date/submission in `review.json` (a blank date is allowed).
2. Start a chat in the tool approved for your work material. Supply `review_template/instructions.md`, the source register, the main PDF, relevant background PDFs, and `review_template/prompts/01_intake.md`. Review the document map and access limitations it returns.
3. Package a small extraction batch:

   ```sh
   python3 scripts/review.py bundle reviews/my-review --sections 3,4,5 --output reviews/my-review/chat-batch.md
   ```

   Upload or paste `chat-batch.md` into that chat. It includes the general instructions, source register, selected field guidance, current section drafts, and extraction prompt. The PDFs must also be accessible in the chat; the bundle does not attach them. If Markdown upload is unavailable, paste its contents. Reduce the batch size if context is limited.
4. Save each returned **REPORT DRAFT block's contents** into its named file under `reviews/my-review/sections/`. Do not save the surrounding chat/code fences. Append **EVIDENCE LOG ADDITIONS** to `evidence.md` and candidate concerns to `issues.md`. Check sources before approving answers.
5. Repeat with sections `6,7,8,9,10`, then `2,11`; split large batches as needed. Use `prompts/03_review_issues.md` with the draft and logs to review candidate concerns. Supply your decisions, then request sections `12,13` and finally `1`. Supply their guidance from `review_template/guidance/` or use another bundle.
6. Run `prompts/04_consistency_check.md` with the assembled draft, evidence log, and accessible sources. Use `prompts/05_handoff.md` if starting a fresh chat; reattach the needed documents.
7. Build a draft and inspect all pages in Word:

   ```sh
   python3 scripts/review.py build reviews/my-review --output output/my-review-draft.docx
   ```

   The build also saves the assembled `.md` for the consistency-check prompt and a `.checks.txt` list of recognized unresolved markers. Only the 13 section files and report metadata enter the report; guidance and logs stay separate.
8. Complete `reviewer_checks.md`, resolve all placeholders, and export:

   ```sh
   python3 scripts/review.py build reviews/my-review --output output/my-review-final.docx --final --reviewer-approved
   ```

   If a reviewed status such as “Not located” legitimately remains, record its disposition and add `--acknowledge-unresolved`. This cannot bypass unfilled `[[...]]`, TODO, or TBD placeholders. The approval flag records your acknowledgment; it does not validate evidence, interpret the checklist, or independently verify calculations. Check the final Word file too.

## What to upload and what to keep

| Item | Purpose |
| --- | --- |
| `instructions.md` + selected guidance or a generated bundle | Reusable chatbot instructions, including the former TeX comments |
| Main searchable protocol PDF | Main source for planned study methods |
| Identified background PDFs | Submission context and historical agreements; conflicts stay explicit |
| Current drafts + evidence/issue logs | Continue extraction and review without losing decisions |
| `sections/*.md` | Working report text; assembled in explicit numeric order |
| `evidence.md` | Source locations/excerpts and dispositions for omitted fields; excluded from Word |
| `issues.md` | Potential concerns and your decisions; excluded from Word |
| `reviewer_checks.md` | Manual evidence, scientific, and page-layout checks |

The templates' examples are instructions only. Never retain their example numbers as submission facts. The sample-size-verification field stays pending until you supply independent verification results. “Not located” is not “None,” and omitted fields need an applicability rationale in the evidence log.

## Formatting and repeated endpoints

Preserve each section's exact first `#` heading. Use `## Endpoint: [actual name]` and repeat the analysis block for each endpoint, giving the evidence entries endpoint-specific IDs. Add named treatment-arm rows/bullets for all arms. Four-space indentation creates nested bullets. A blank line separates paragraphs, headings, lists, and tables.

Simple tables and standard math convert to native, editable Word objects. For example:

```markdown
| Arm | Regimen | Allocation |
| --- | --- | --- |
| Experimental | State the actual regimen | State the actual allocation |
| Control | State the actual regimen | State the actual allocation |

$H_0: \mathrm{HR}=1$ versus $H_1: \mathrm{HR}\ne1$.
```

Keep detailed endpoint analyses as subsections rather than large table cells. Merged cells, lists inside tables, raw HTML/TeX layout, and embedded images are outside the initial workflow. Insert a complex schematic in Word after export if needed. Regenerating a report overwrites that output and does not preserve manual Word edits; retain the final edited Word file separately.

Single-arm studies omit inapplicable comparative fields; retain the intervention description. Confirmed no interim analyses becomes “None.” For medical/regulatory sample sizing, retain the first sizing bullet and explanation and remove the calculation bullets. Section 11's heading remains in the automatic 13-section build; if appropriate, remove that section manually in the final Word document, following the original template's instruction. Personal reference appendices are kept separately and inserted manually if desired.

The reference document controls styles and page setup, with local normalization of list/table geometry. See `review_template/STYLE.md` for exact settings. You can pass `--reference-doc path/to/custom.docx`; the documented review list/table/style contract still applies. If the chatbot later offers Word downloads, keep the same evidence/approval process and compare its output with this local build.

## Synthetic example and verification

`examples/synthetic_review/` contains fictional protocol/background text, a completed draft, and evidence/issue logs. Its source documents are Markdown; it tests local assembly rather than chatbot PDF retrieval. `examples/synthetic_review/example_report.docx` demonstrates nested bullets, three arms, multiple endpoints, a table, and editable math. It is a formatting/workflow example, not a scientific recommendation or independent sample-size verification.

The supplied Word files were structurally checked with Pandoc 3.12.1. LibreOffice was unavailable here, so rendered page QA could not be completed; open them in Word and inspect every page before adopting the layout.

To run the checks:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/review.py build examples/synthetic_review --output output/synthetic-draft.docx
```

Set `PANDOC` to an executable path for the integration tests if it is not on PATH. Builds accept `--pandoc /path/to/pandoc`. Tests skip only the Word conversion cases when Pandoc is unavailable; text validation still runs.

To maintain the reusable template, edit `review_template/sections.json` (field definitions and rules) and run `python3 scripts/refresh_templates.py` to regenerate blank sections and guidance. Do not edit generated guidance in isolation. To rebuild the Word reference, run `python3 scripts/make_reference.py`. The original TeX is preserved as historical reference; Markdown is the working master.
