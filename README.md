# Protocol Review

A guided, local workflow for using Elsa to retrieve protocol facts, verify every answer against its source, and generate an editable statistical review memo. Statistical evaluation, deficiencies, independent calculation checks, and reviewer conclusions remain the reviewer's responsibility.

## Start on a Windows work computer

1. Copy or clone this whole folder to the computer.
2. Double-click **`setup_ui.bat`** once. It creates an isolated `.venv` and installs the two direct UI packages in `requirements-ui.txt` plus their required dependencies.
3. Double-click **`start_ui.bat`** whenever you want to work. Your browser opens the app at `http://127.0.0.1:8501`.
4. Keep the terminal window open while using the app. Closing it stops the local app; saved work remains under `reviews/`.

The app has four screens:

1. **Set up** — create a review and upload the protocol/background PDFs once.
2. **Exchange with Elsa** — prepare a small extraction request, take the instructions and PDFs to Elsa, then load Elsa's JSON response.
3. **Review sections** — edit answers, inspect the cited PDF page, save drafts, and explicitly approve a whole section.
4. **Export** — download Markdown at any time or create a draft/final Word memo when Pandoc is available.

Start with **Try fictional example** to learn the review controls without a protocol or Elsa. It loads simulated results and approves nothing. The app runs only on the local loopback address, has no Elsa API integration, and disables Streamlit usage telemetry.

See [the complete UI guide](docs/STREAMLIT_UI.md), including work-computer testing and the Pandoc-optional path.

## What the workflow protects

- Elsa's original JSON, proposed text, reviewer edits, and approved text are kept separately.
- Every extracted fact retains its document version, exact excerpt, section, and PDF position.
- Editing or saving does not imply approval. **Approve section and continue** validates the entire section before accepting it.
- Reloading the same JSON does not duplicate proposals or overwrite saved edits.
- Replacing a protocol preserves the old file and prevents its evidence from being displayed against a different version.
- A final Word build remains locked until all required factual and manual fields have approved dispositions and the reviewer signs off.

The software can validate structure and provenance, but it cannot establish quotation fidelity, retrieval completeness, scientific accuracy, or Word page layout. Check the cited source and inspect every page in Word.

## Pandoc and Word output

Pandoc is needed only for `.docx` output. Set up, Elsa exchange, review, saved drafts, and Markdown export work without it. If Pandoc is installed in a nonstandard location, enter its executable path once under **Export → Word settings**.

## Command-line workflow

The existing CLI remains available for advanced use and automation; the UI and CLI use the same review workspaces. See the [Stage A command reference](docs/STAGE_A.md). Existing section-based reviews are not migrated; see the [legacy workflow](docs/LEGACY_WORKFLOW.md).

Other references:

- [Fictional pilot and expected results](examples/stage_a/README.md)
- [Complete field catalog](review_template/stage_a/FIELD_CATALOG.md)

## Validation

```sh
python3 -m unittest discover -s tests -v
```

Set `PANDOC` to an executable path to include the real Word-conversion integration tests; otherwise those tests skip. UI interaction tests require the packages in `requirements-ui.txt`.
