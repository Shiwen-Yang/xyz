# Guided UI workflow

The UI replaces routine terminal commands and folder navigation with four browser screens. It is a local single-reviewer application: it does not call Elsa, upload files to a cloud service, or require an API. Moving the instructions and response between this app and Elsa remains a manual step.

## One-time setup on the work computer

Prerequisites:

- Windows with Python 3.11 or newer and the `py` launcher.
- Permission to install the pinned packages in `requirements-ui.txt` into this project's private `.venv`.
- A current browser.
- Pandoc only if Word output is being tested.

Double-click `setup_ui.bat`. It creates `.venv` beside the project and installs Streamlit and the local PDF-viewer component there. It does not change the system Python environment. If package installation is controlled by your organization, give IT `requirements-ui.txt` and ask for the approved internal package source or installation procedure.

Then double-click `start_ui.bat`. It starts the app only on `127.0.0.1` and opens `http://127.0.0.1:8501`. Keep the terminal window open. Closing it stops the app, but does not delete saved work.

If port 8501 is already occupied, close the other Streamlit process before starting this app.

## First test without a protocol or Pandoc

This confirms the review controls and local persistence without using proprietary files.

1. Open the app and choose **Try fictional example**.
2. In **Review sections**, change one `Memo wording` box.
3. Click **Save section draft**. Move to **Export**, then return to **Review sections** and confirm the edit remains.
4. Click **Approve section and continue** and confirm the app advances to the next section.
5. Close the terminal, run `start_ui.bat` again, select the fictional review in the sidebar, and confirm the approved wording remains.
6. On **Export**, download **draft Markdown**. Word generation can wait until Pandoc is approved.

The fictional example uses text sources, not a PDF. It is useful for workflow testing but does not test Elsa, PDF rendering, or retrieval accuracy.

## PDF-viewer test without a real protocol

After organizational approval, use a non-proprietary PDF whose pages can be freely inspected. A public guidance document or a locally created multi-page PDF is suitable.

1. Create a new review and upload that PDF as the main protocol on **Set up**.
2. Prepare instructions on **Exchange with Elsa**. Confirm the instructions can be copied/downloaded and the same PDF is offered for download.
3. Do not expect meaningful extraction unless Elsa is given both the instructions and the test PDF.
4. If you do run the Elsa test, load its JSON, open a field's **Evidence**, and click **View source**.
5. Confirm the embedded viewer opens the cited PDF position. Compare the exact excerpt and section manually.

The app distinguishes the 1-based PDF position from any printed page label. A source replacement is retained as a new version; old evidence remains tied to the old bytes.

## Routine review

### 1. Set up

Create a named review, enter the reviewer's name, and upload the main protocol. Background PDFs are optional. Documents are copied into the review workspace, so you do not need to revisit their original folders.

### 2. Exchange with Elsa

Use the suggested small batch. Click **Prepare instructions**, copy or download the displayed instructions, and attach every listed PDF in the same Elsa conversation. Ask Elsa to export its response as JSON; then return and use **Load response**.

The app rejects malformed, incomplete, unmatched, or structurally invalid responses before changing review content. Re-loading identical bytes is harmless. Use a new extraction request when the protocol or accepted endpoint inventory changes.

### 3. Review sections

For each answer:

- compare the memo wording with the exact source excerpt;
- click **View source** to open the cited PDF position;
- correct wording or choose not to include it, with a reason where required;
- use **Save section draft** if you are not ready to approve; and
- use **Approve section and continue** only after checking every field in the section.

Saved drafts survive navigation and restart but block final readiness until approved. New Elsa proposals do not silently replace earlier accepted wording; choose the new proposal explicitly if you want to adopt it.

Sections 11–13 and the assessment portion of section 1 are manual reviewer work. Elsa is used for factual retrieval and factual summary, not statistical deficiency identification or conclusions.

### 4. Export

**Create draft Word** is available before the review is complete and marks unresolved content in the assembled memo. **Create final Word** requires all required decisions, a current factual executive summary, the manual sections, and the final reviewer checkbox.

Word output requires Pandoc. If it is authorized but not on `PATH`, expand **Word settings**, enter the full path to `pandoc.exe`, and click **Remember Word setting**. Markdown remains available without Pandoc.

Always open the resulting `.docx` in Word and inspect tables, lists, pagination, equations, and every page. Regenerating the report does not preserve edits made only inside a previous Word copy.

## Where files are stored

Each review has its own folder under `reviews/`. The UI manages its inputs, Elsa request packages, raw response archives, saved drafts, decisions, and generated exports. These directories are Git-ignored by default. Do not hand-edit `stage_a/state.json` or the archived JSON files.

Back up the whole review folder if organizational policy permits. Do not rely on the browser session as the record: the files in that folder are the persistent record.

## Troubleshooting

- **The launcher says Python is missing:** install an approved Python 3.11+ distribution that supplies the Windows `py` launcher.
- **Setup cannot download packages:** use the organization's approved package mirror or ask IT to install `requirements-ui.txt` into `.venv`.
- **The browser does not open:** while the terminal remains open, visit `http://127.0.0.1:8501` manually.
- **The app will not start:** check whether another application is using port 8501 and review the terminal messages.
- **Word conversion fails:** continue with Markdown, then enter the approved `pandoc.exe` path under Word settings after Pandoc is installed.
- **A response is rejected:** confirm it was produced from the currently selected review's most recent instructions and that all requested fields are present.
- **A PDF citation looks wrong:** do not approve it. Correct the response through a fresh extraction request or edit the memo wording only after verifying the exact source yourself.

For advanced recovery and command-line operations, see [Stage A walkthrough](STAGE_A.md).
