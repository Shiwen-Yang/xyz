# Protocol Review

A guided, local workflow for using Elsa to retrieve protocol facts, verify every answer against its source, and generate an editable statistical review memo. Statistical evaluation, deficiencies, independent calculation checks, and reviewer conclusions remain the reviewer's responsibility.

## Start on Linux or WSL

Needs Python 3.10+ (with `python3-venv` on Ubuntu/Debian: `sudo apt install python3-venv`). Keep the project on the Linux filesystem (e.g. under `~`), not under `/mnt/c`.

1. Run `./setup_ui.sh` once. It creates an isolated `.venv` and installs the three direct UI packages in `requirements-ui.txt` plus their required dependencies.
2. Run `./start_ui.sh` whenever you want to work. It serves the app at `http://127.0.0.1:8501` and tries to open your browser. In WSL2 that address is forwarded to your Windows browser; if no browser opens, visit it manually (`sudo apt install wslu` lets the launcher open the Windows browser itself).
3. Keep the terminal open while using the app; Ctrl+C stops it. Saved work remains under `reviews/`.

Windows launchers (`.bat`) are kept in `legacy/windows/`.

The app follows one fixed workflow, with a progress indicator along the top (Set up → Review workspace → Export):

1. **Set up** — create a review (or continue a saved one) and upload the protocol/background PDFs once.
2. **Review workspace** — the source PDF on the left; the template's 13 sections on the right. **Primary Objective(s)** is the first section built. It walks through three steps with Back/Next buttons: copy the prompt for Elsa, load Elsa's JSON (from your downloads folder, an upload, or pasted text), then check each extracted objective. Every objective is a collapsible bulletin with an editable box: **Locate reference** jumps the PDF to the cited passage and highlights it, **Looks good** approves the wording (the bulletin collapses with a check mark), and **↻** resets it to Elsa's text. Finishing the section puts a green check on its header.
3. **Export** — a memo check with the PDF beside it. Each bulletin the memo will contain can be located in the PDF, marked **Looks right**, or flagged; a flagged bulletin is reopened in the Review workspace. When every bulletin is checked and none is flagged, **All Set** unlocks Markdown and Word downloads (Word needs Pandoc).

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

Pandoc is needed only for `.docx` output (`sudo apt install pandoc` in WSL). Set up, Elsa exchange, review, saved drafts, and Markdown export work without it. If Pandoc is installed in a nonstandard location, enter its executable path once under **Export → Word settings**.

## Command-line workflow

The CLI remains available for advanced use and automation; the UI and CLI use the same review workspaces. See the [Stage A command reference](docs/STAGE_A.md).

Other references:

- [Fictional pilot and expected results](examples/stage_a/README.md)
- [Complete field catalog](review_template/stage_a/FIELD_CATALOG.md)

## Validation

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Set `PANDOC` to an executable path to include the real Word-conversion integration tests; otherwise those tests skip. UI interaction tests require the packages in `requirements-ui.txt`, so run the tests with the `.venv` Python.

## Repository layout

| Path | Contents |
| --- | --- |
| `app.py`, `.streamlit/` | Streamlit UI |
| `scripts/` | `review.py` (CLI), `stage_a.py` (workflow engine), `ui_service.py`, `start_ui.py`, `word_style.py`, `demo_stage_a.py`, catalog/reference generators |
| `review_template/` | Stage A field catalog and instructions, shared `sections.json`, Word reference style, reviewer checklist |
| `docs/` | UI guide and Stage A command reference |
| `examples/stage_a/` | Fictional pilot: sources and simulated Elsa response |
| `tests/` | Test suite (`tests/fixtures/sample.pdf` is a sample PDF for the UI tests) |
| `legacy/` | Superseded work, kept for reference: the original section-based Markdown workflow, the LaTeX memo template, and Windows launchers. See [legacy/README.md](legacy/README.md) |
