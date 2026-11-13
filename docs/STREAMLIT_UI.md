# Guided UI workflow

The UI replaces routine terminal commands and folder navigation with three browser screens. It is a local single-reviewer application: it does not call Elsa, upload files to a cloud service, or require an API. Moving the instructions and response between this app and Elsa remains a manual step.

## One-time setup on the work computer

Prerequisites:

- Linux or WSL with Python 3.10 or newer and the `venv` module (Ubuntu/Debian: `sudo apt install python3-venv`).
- Permission to install the pinned packages in `requirements-ui.txt` into this project's private `.venv`.
- A current browser (under WSL2, the Windows browser reaches the app through localhost forwarding).
- Pandoc only if Word output is being tested.

Run `./setup_ui.sh`. It creates `.venv` beside the project and installs Streamlit and the local PDF-viewer component there. It does not change the system Python environment. If package installation is controlled by your organization, give IT `requirements-ui.txt` and ask for the approved internal package source or installation procedure.

Then run `./start_ui.sh`. It starts the app only on `127.0.0.1` and opens `http://127.0.0.1:8501`. Keep the terminal open; Ctrl+C stops the app but does not delete saved work. On Windows without WSL, use the launchers in `legacy/windows/`.

If port 8501 is already occupied, close the other Streamlit process before starting this app.

## First test without a protocol or Pandoc

1. Open the app and choose **Try fictional example**. It opens the **Review workspace** with simulated results.
2. Expand **3. Primary Objective(s)** on the right and confirm the simulated objectives appear as references. The fictional example uses text sources, not a PDF, so there is no page to highlight.
3. On **Export**, download **draft Markdown**. Word generation can wait until Pandoc is approved.

## PDF and highlight test without a real protocol

Use a non-proprietary PDF whose pages can be freely inspected, after organizational approval.

1. Create a new review and upload that PDF as the main protocol on **Set up**.
2. In **Review workspace**, open **3. Primary Objective(s)** and click **Prepare prompt**. Click **Copy prompt to clipboard** (or use the text box) and confirm the same PDF is offered for download.
3. Run the exchange in Elsa with that PDF, then load the JSON response.
4. Click a reference. The PDF should open at the page and outline the quoted passage. Compare it with the excerpt shown.

The app distinguishes the 1-based PDF position from any printed page label. A source replacement is retained as a new version; old evidence remains tied to the old bytes.

## Routine review

### 1. Set up

Create a named review, enter the reviewer's name, and upload the main protocol. Background PDFs are optional. Documents are copied into the review workspace, so you do not need to revisit their original folders.

### 2. Review workspace

The left panel is the source PDF. The right panel lists the template sections; only **Primary Objective(s)** works so far.

Each section works as a short panel: one step is shown at a time, **Next →** unlocks when the step is done, and earlier steps are hidden once you move on (use **← Back** to return).

1. **Prompt for Elsa.** Click **Prepare prompt**, then **Copy prompt to clipboard**. If your browser blocks copying, open **Show prompt text** and copy from the box. Paste it into Elsa and attach the listed PDFs in the same chat. The prompt asks Elsa to name its download `elsa_<request id>.json`.
2. **Bring the response back.** Three equal options: **Downloads folder** (set your browser's download folder once; the app finds the newest file with that name, and under WSL it suggests your Windows Downloads folder), **Upload file**, or **Paste JSON**.
3. **References.** Objectives are grouped as primary, secondary, and other (for example exploratory), following the sponsor's own labels. Each lists its sources. Clicking one opens the PDF at the cited page and outlines the passage. The mark beside each reference reports the match: found on the cited page, only partly found, found on a different page than cited, or not found in the PDF's text (for example a scanned page). Reviews created before the "other objectives" field existed are refreshed automatically if nothing has been approved. Elsa returns a page and an exact excerpt but no coordinates, so the highlight comes from searching the page's text layer. A match shows where the text is; it does not mean the extraction is correct.

The app rejects malformed, incomplete, unmatched, or structurally invalid responses before changing review content. Re-loading identical bytes is harmless.

This screen is read-only for now. Editing, saving and approving answers will return as more sections are built, so final Word output stays locked until then; draft output still works.

### 3. Export

**Create draft Word** is available before the review is complete and marks unresolved content in the assembled memo. **Create final Word** requires all required decisions, a current factual executive summary, the manual sections, and the final reviewer checkbox.

Word output requires Pandoc. If it is authorized but not on `PATH`, expand **Word settings**, enter the full path to the `pandoc` executable, and click **Remember Word setting**. Markdown remains available without Pandoc.

Always open the resulting `.docx` in Word and inspect tables, lists, pagination, equations, and every page. Regenerating the report does not preserve edits made only inside a previous Word copy.

## Where files are stored

Each review has its own folder under `reviews/`. The UI manages its inputs, Elsa request packages, raw response archives, saved drafts, decisions, and generated exports. These directories are Git-ignored by default. Do not hand-edit `stage_a/state.json` or the archived JSON files.

Back up the whole review folder if organizational policy permits. Do not rely on the browser session as the record: the files in that folder are the persistent record.

## Troubleshooting

- **Setup says Python or venv is missing:** install Python 3.10+ (`sudo apt install python3 python3-venv` on Ubuntu/Debian).
- **Setup cannot download packages:** use the organization's approved package mirror or ask IT to install `requirements-ui.txt` into `.venv`.
- **The browser does not open:** while the terminal remains open, visit `http://127.0.0.1:8501` manually. In WSL, `sudo apt install wslu` lets the launcher open the Windows browser.
- **The app will not start:** check whether another application is using port 8501 and review the terminal messages.
- **Word conversion fails:** continue with Markdown, then install Pandoc (or enter the approved executable path) under Word settings after Pandoc is installed.
- **A response is rejected:** confirm it was produced from the currently selected review's most recent instructions and that all requested fields are present.
- **A PDF citation looks wrong:** do not approve it. Correct the response through a fresh extraction request or edit the memo wording only after verifying the exact source yourself.

For advanced recovery and command-line operations, see [Stage A walkthrough](STAGE_A.md).
