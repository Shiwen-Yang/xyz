# Statistical review memo: Elsa Stage A

Use Elsa to retrieve sponsor statements and factual summaries, verify the results locally, and generate an editable Word memo. Statistical evaluation, deficiencies, independent calculation verification, and reviewer conclusions remain manual.

**Prepare request → upload to Elsa → download JSON → validate/import → verify/edit fields → build Word.** Uploading and downloading are manual; the scripts use no Elsa API or network service.

Python 3.9+ is required, with no pip packages. Pandoc is required for Word output; preparation, import, review, and Markdown output work without it. On Windows, use `python` if that is your Python command.

## Start with the fictional pilot

```sh
python3 scripts/demo_stage_a.py reviews/stage-a-demo
python3 scripts/review.py review reviews/stage-a-demo
```

This prepares a request and imports a **simulated** Elsa response without approving any content. It does not test Elsa or call a model. Open the resulting `stage_a/verification.md`, edit individual field text files, and explicitly accept or reject candidates.

- [Stage A walkthrough and command reference](docs/STAGE_A.md)
- [Fictional pilot and expected results](examples/stage_a/README.md)
- [Complete field catalog](review_template/stage_a/FIELD_CATALOG.md)
- [Legacy Markdown workflow](docs/LEGACY_WORKFLOW.md)

## New reviews

```sh
python3 scripts/review.py init reviews/my-review
python3 scripts/review.py source reviews/my-review reviews/my-review/protocol.pdf --id PROTOCOL --role protocol --version "1.0" --date "2026-01-15"
python3 scripts/review.py prepare reviews/my-review --sections 3,4,5
```

Place the actual protocol at the registered path first. Upload the generated request instructions and listed documents to Elsa, then import its downloaded JSON. Follow the walkthrough to review fields and build Word. Keep submissions and working files in Git-ignored `reviews/` and reports in `output/`.

Existing section-based reviews are not migrated. Create another with `init ... --workflow legacy`; `bundle` remains available only for that workflow. Original TeX files remain unchanged.

## Validation

```sh
python3 -m unittest discover -s tests -v
```

Set `PANDOC` to an executable path for the actual Word integration tests if necessary; otherwise those tests skip. Structural checks cannot prove quotation fidelity, retrieval completeness, scientific accuracy, or Word page layout. Check sources and inspect every page in Word. Long/complex protocol performance and Elsa processing limits remain untested.
