"""A local, guided workspace for statistical review memos."""
from pathlib import Path
import json
import shutil
import sys

import streamlit as st
from streamlit_pdf_viewer import pdf_viewer

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
import pdf_locate
import stage_a as sa
import ui_service as svc

SCREENS = ["Set up", "Review workspace", "Export"]
st.set_page_config(page_title="Protocol Review", page_icon="📄", layout="wide")


def notice(message):
    st.session_state["notice"] = message


def navigate(screen, section=None):
    st.session_state["screen"] = screen
    if section is not None:
        st.session_state["section"] = section


def move(screen, section=None):
    st.session_state["next_screen"] = screen
    if section is not None:
        st.session_state["next_section"] = section
    st.rerun()


def error(exc, workspace=None):
    st.error(svc.friendly_error(exc, workspace))


def setup(workspace):
    st.header("Set up your review")
    st.write("Add your documents once. Your work will be saved on this computer.")
    with st.expander("New review or fictional example", expanded=workspace is None):
        with st.form("create_review"):
            name = st.text_input("Review name", placeholder="Protocol review — study name")
            reviewer = st.text_input("Your name")
            a, b = st.columns(2)
            create = a.form_submit_button("Create review", type="primary")
            demo = b.form_submit_button("Try fictional example")
        if create or demo:
            try:
                path = svc.create_review(name or ("Fictional example" if demo else ""), reviewer or ("Test reviewer" if demo else ""), demo=demo)
                st.session_state["workspace"] = str(path)
                st.session_state.pop("review_picker", None)
                notice("Fictional results loaded for practice. No answers have been approved." if demo else "Review created. Add the main protocol below.")
                move("Review workspace" if demo else "Set up")
            except (ValueError, OSError) as exc:
                error(exc)
    if workspace is None:
        return
    config = sa.read_json(workspace / "review.json")
    state = sa.load(workspace)
    with st.expander("Review details"):
        with st.form("metadata:" + workspace.name):
            name = st.text_input("Review name", value=config.get("ui_name", config["submission"]))
            reviewer = st.text_input("Reviewer", value=config.get("ui_reviewer", ""))
            author = st.text_input("Report author / office", value=config["author"])
            date = st.text_input("Report date (optional)", value=config["date"])
            saved = st.form_submit_button("Save details")
        if saved:
            try:
                svc.update_metadata(workspace, name, reviewer, author, date)
                notice("Review details saved.")
                st.rerun()
            except (ValueError, OSError) as exc:
                error(exc, workspace)
    st.subheader("Documents")
    if state["sources"]:
        for source in state["sources"].values():
            st.write(f"**{source['filename']}** · {'Main protocol' if source['role'] == 'protocol' else 'Background'} · version {source['version']}")
    with st.form("documents:" + workspace.name, clear_on_submit=True):
        main = st.file_uploader("Main protocol PDF", type=["pdf"])
        background = st.file_uploader("Background PDFs (optional)", type=["pdf"], accept_multiple_files=True)
        with st.expander("Document version and date (optional)"):
            version = st.text_input("Main protocol version", placeholder="Unknown if left blank")
            date = st.text_input("Main protocol date", placeholder="Unknown if left blank")
        if "PROTOCOL" in state["sources"]:
            st.caption("Adding a different main protocol keeps the old file, but previous answers may need to be extracted again.")
        uploaded = st.form_submit_button("Save documents", type="primary")
    if uploaded:
        try:
            if main is None and not background:
                raise ValueError("Choose at least one document to add.")
            if main:
                svc.store_source(workspace, main.name, main.getvalue(), "protocol", version, date)
            for source in background or []:
                svc.store_source(workspace, source.name, source.getvalue(), "background")
            notice("Documents saved. You can now prepare the prompt for Elsa.")
            st.rerun()
        except (ValueError, OSError) as exc:
            error(exc, workspace)
    st.button("Next: review workspace →", on_click=navigate, args=("Review workspace",), disabled=not state["sources"])


@st.cache_data(show_spinner=False)
def locate_excerpt(path, sha, page, excerpt):
    return pdf_locate.locate(path, page, excerpt)


def copy_button(text, label="Copy prompt to clipboard"):
    """Browsers only allow clipboard writes from a click inside the page."""
    payload = json.dumps(text).replace("</", "<\\/")
    st.iframe("""
<button id="b" style="font:600 14px system-ui;padding:8px 14px;border-radius:6px;border:1px solid #888;cursor:pointer">""" + label + """</button>
<span id="s" style="font:14px system-ui;margin-left:10px"></span>
<script>
const text = """ + payload + """;
const s = document.getElementById('s');
function legacy() {
  const t = document.createElement('textarea'); t.value = text; document.body.appendChild(t); t.select();
  let ok = false; try { ok = document.execCommand('copy'); } catch (e) {}
  document.body.removeChild(t); return ok;
}
document.getElementById('b').onclick = async () => {
  let ok = false;
  try { await navigator.clipboard.writeText(text); ok = true; } catch (e) { ok = legacy(); }
  s.textContent = ok ? 'Copied.' : 'Your browser blocked copying - select the text below and copy it.';
};
</script>""", height=52)


def focus_reference(version_key, path, page, excerpt):
    """Button callback: aim the PDF panel at a cited passage and highlight it."""
    found = locate_excerpt(path, svc_sha(path), page, excerpt) if path else dict(status="unavailable", page=page, rects=[])
    shown = found["page"] if found["status"] in ("exact", "partial", "other_page") else (page or 1)
    st.session_state["source_version"] = version_key
    st.session_state["pdf_page"] = shown
    st.session_state["highlight"] = dict(page=shown, rects=found["rects"], status=found["status"])


def svc_sha(path):
    return sa.file_hash(Path(path))


def pdf_panel(workspace):
    sources = svc.source_versions(workspace)
    st.subheader("Source document")
    if not sources:
        st.info("Upload a document in Set up to view its pages here.")
        return
    if st.session_state.get("source_version") not in sources:
        st.session_state["source_version"] = next(iter(sources))
    source_id = st.selectbox("Document", list(sources), key="source_version",
        format_func=lambda k: sources[k]["filename"] + " · v" + sources[k]["version"] + (" (earlier version)" if not sources[k]["current"] else ""))
    source = sources[source_id]
    path = Path(source["path"])
    if not path.exists():
        st.error("This exact source version is unavailable. Its evidence is retained, but do not compare it against a different version. Add the original file again or re-extract from the current protocol.")
        return
    if sa.file_hash(path) != source["sha256"]:
        st.error("The source file has changed since it was registered. Add the current document in Set up before continuing.")
        return
    if path.suffix.lower() != ".pdf":
        st.caption("This fictional example uses text sources. Real PDF uploads display here at the cited page.")
        st.text_area("Source text", path.read_text(encoding="utf-8"), height=600, disabled=True, key="source_text:" + source_id)
        return
    maximum = source["pdf_pages"]
    current = max(1, int(st.session_state.get("pdf_page", 1)))
    st.session_state["pdf_page"] = min(current, maximum) if maximum else current
    page = st.number_input("PDF page position", min_value=1, max_value=maximum, key="pdf_page")
    full = st.checkbox("Show full document", key="full_pdf")
    highlight = st.session_state.get("highlight") or {}
    annotations = [dict(page=highlight["page"], color="#e6a700", border="solid", **r) for r in highlight.get("rects", [])] \
        if highlight.get("page") else []
    if highlight.get("status") == "not_found" and highlight.get("page") == page:
        st.warning("The cited excerpt was not found in this page's text, so nothing is highlighted. Read the page directly.")
    elif highlight.get("status") == "other_page" and highlight.get("page") == page:
        st.info("This passage was found here, on a different page than Elsa cited.")
    pdf_viewer(path.read_bytes(), height=720,
               key="pdf:" + workspace.name + source_id + source["sha256"][:12] + (":full" if full else ":" + str(page)) + ":" + str(len(annotations)) + str(highlight.get("page")),
               pages_to_render=[] if full else [page], annotations=annotations, annotation_outline_size=3,
               scroll_to_page=page if full else None, render_text=True, zoom_level="auto")
    st.download_button("Download source PDF", path.read_bytes(), file_name=source["filename"], mime="application/pdf")


def load_response(workspace, data):
    try:
        run_id, created = svc.import_bytes(workspace, data)
        notice("Response loaded. Click a reference to see it in the PDF." if created else "This response is already loaded. Nothing changed.")
        st.rerun()
    except (ValueError, OSError, UnicodeDecodeError) as exc:
        error(exc, workspace)


def set_step(key, index):
    st.session_state[key] = index


def stepper(workspace, name, steps):
    """Show one step of a section at a time; earlier steps are hidden once you move on.

    ``steps`` is a list of ``(title, render, can_continue)``; Next stays disabled
    until ``can_continue()`` is true after the step has rendered.
    """
    key = f"step:{workspace.name}:{name}"
    last = len(steps) - 1
    index = max(0, min(int(st.session_state.get(key, 0)), last))
    title, render, can_continue = steps[index]
    st.progress((index + 1) / len(steps), text=f"Step {index + 1} of {len(steps)} · {title}")
    render()
    st.divider()
    back, forward = st.columns(2)
    back.button("← Back", key=key + ":back", disabled=index == 0, on_click=set_step, args=(key, index - 1), use_container_width=True)
    forward.button("Next →" if index < last else "Last step", key=key + ":next", type="primary",
                   disabled=index == last or not can_continue(), on_click=set_step, args=(key, index + 1), use_container_width=True)


def step_prompt(workspace):
    state = sa.load(workspace)
    request_id = svc.objectives_request(workspace)
    st.caption("Asks Elsa for every primary, secondary and other (for example exploratory) objective, quoted word for word with its source page. Each objective is sorted by the sponsor's own label.")
    if not request_id:
        if st.button("Prepare prompt", type="primary", key="prepare:" + workspace.name):
            try:
                svc.prepare_objectives(workspace)
                st.rerun()
            except (ValueError, OSError) as exc:
                error(exc, workspace)
        return
    prompt = svc.elsa_prompt(workspace, request_id)
    manifest = state["requests"][request_id]
    copy_button(prompt)
    with st.expander("Show prompt text (fallback if copying is blocked)"):
        st.code(prompt, language="markdown", height=220)
        st.download_button("Download prompt", prompt, file_name="elsa-prompt.md", mime="text/markdown", key="promptdl:" + request_id)
    st.caption("Paste it into Elsa and attach these documents in the same chat:")
    for source_id, meta in manifest["sources"].items():
        source = state["sources"].get(source_id)
        columns = st.columns([3, 1])
        columns[0].write("• " + meta["filename"])
        if source and Path(source["path"]).is_file():
            columns[1].download_button("Download", Path(source["path"]).read_bytes(), file_name=meta["filename"], key="docdl:" + source_id + request_id)
    st.caption("When Elsa has answered, ask it to download the JSON, then click Next.")


def step_response(workspace):
    request_id = svc.objectives_request(workspace)
    filename = svc.elsa_filename(request_id)
    st.caption("The prompt asks Elsa to name its download `" + filename + "`.")
    folder_tab, upload_tab, paste_tab = st.tabs(["Downloads folder", "Upload file", "Paste JSON"])
    with folder_tab:
        folder = st.text_input("Folder where your browser saves downloads", value=svc.download_dir(workspace), key="folder:" + workspace.name)
        if st.button("Load response from this folder", type="primary", key="loadfolder:" + workspace.name):
            try:
                found = svc.find_download(folder, request_id)
                svc.remember_download_dir(workspace, folder)
                load_response(workspace, found.read_bytes())
            except (ValueError, OSError) as exc:
                error(exc, workspace)
    with upload_tab:
        uploaded = st.file_uploader("Elsa response JSON", type=["json"], key="upload:" + workspace.name)
        if st.button("Load uploaded file", disabled=uploaded is None, key="loadupload:" + workspace.name):
            load_response(workspace, uploaded.getvalue())
    with paste_tab:
        pasted = st.text_area("Paste Elsa's JSON", height=140, key="paste:" + workspace.name)
        if st.button("Load pasted JSON", disabled=not pasted.strip(), key="loadpaste:" + workspace.name):
            load_response(workspace, pasted.encode("utf-8"))
    if svc.objective_references(workspace):
        st.success("A response is loaded. Click Next to see the references.")


def step_references(workspace):
    references = svc.objective_references(workspace)
    st.caption("Click a reference to open the PDF at that passage. A match only shows where the text was found; you still read and verify it.")
    marks = {"exact": "✅", "partial": "⚠️", "other_page": "⚠️", "not_found": "❌", "unavailable": "▫️"}
    for identifier, heading in svc.OBJECTIVE_GROUPS:
        st.markdown("#### " + heading)
        group = [r for r in references if r["key"].startswith(identifier + "/")]
        if not group:
            st.caption("None returned.")
        for ref in group:
            with st.container(border=True):
                st.markdown("**" + ref["label"] + "**")
                if ref["value"]:
                    st.write(ref["value"])
                else:
                    st.caption(ref["status"].replace("_", " ").capitalize() + (" — " + ref["explanation"] if ref["explanation"] else ""))
                for index, source in enumerate(ref["sources"]):
                    usable = source["path"] and Path(source["path"]).is_file()
                    found = locate_excerpt(source["path"], svc_sha(source["path"]), source["pdf_page"], source["exact_excerpt"]) if usable else dict(status="unavailable")
                    where = "p. " + str(source["pdf_page"]) if source["pdf_page"] else "page not given"
                    st.button(f"{marks[found['status']]} {where} · {source['section'] or 'section not given'}", key=f"ref:{ref['key']}:{index}",
                              help=pdf_locate.LABELS[found["status"]], on_click=focus_reference,
                              args=(source["version_key"], source["path"], source["pdf_page"], source["exact_excerpt"]))
                    st.caption(pdf_locate.LABELS[found["status"]])
                    st.markdown("> " + source["exact_excerpt"].replace("\n", " "))


def objectives_section(workspace):
    stepper(workspace, "objectives", [
        ("Prompt for Elsa", lambda: step_prompt(workspace), lambda: svc.objectives_request(workspace) is not None),
        ("Bring Elsa's response back", lambda: step_response(workspace), lambda: bool(svc.objective_references(workspace))),
        ("References", lambda: step_references(workspace), lambda: False),
    ])


def review_workspace(workspace):
    st.header("Review workspace")
    catalog = sa.catalog(workspace)
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        pdf_panel(workspace)
    with right:
        st.subheader("Template sections")
        with st.container(height=900):
            for section in catalog["sections"]:
                number, title = section["number"], section["title"].rstrip(": ")
                active = number == svc.OBJECTIVES_SECTION
                with st.expander(f"{number}. {title}", expanded=active):
                    if active:
                        objectives_section(workspace)
                    else:
                        st.caption("Not available in this workspace yet.")


def export(workspace):
    st.header("Export your memo")
    blockers = sa.readiness(workspace)
    if blockers:
        st.info(f"{len(blockers)} items still need attention. You can download a draft now.")
        with st.expander("Go to unfinished work"):
            seen = set()
            fields = sa.fields(workspace)
            for message in blockers:
                matched = next((f for identifier, f in fields.items() if identifier in message), None)
                if matched and matched["section"] not in seen:
                    seen.add(matched["section"])
                    st.button("Review " + str(matched["section"]) + ": " + next(s["title"] for s in sa.catalog(workspace)["sections"] if s["number"] == matched["section"]), key="block:" + str(matched["section"]), on_click=navigate, args=("Review workspace",))
                elif not matched:
                    st.write(svc.friendly_error(message, workspace))
    _, body, _ = sa.assemble(workspace)
    with st.expander("Memo preview", expanded=True):
        with st.container(height=440):
            st.markdown(body)
    config = sa.read_json(workspace / "review.json")
    pandoc = shutil.which("pandoc")
    with st.expander("Word settings"):
        pandoc = st.text_input("Pandoc executable (if not on PATH)", value=config.get("ui_pandoc") or pandoc or "pandoc")
        if st.button("Remember Word setting"):
            config["ui_pandoc"] = pandoc
            sa.write_json(workspace / "review.json", config)
            st.success("Word setting saved.")
    final_ok = st.checkbox("I have completed source/scientific review and checked the Word page layout", disabled=bool(blockers))
    a, b = st.columns(2)
    draft = a.button("Create draft Word", type="primary")
    final = b.button("Create final Word", disabled=bool(blockers) or not final_ok)
    if draft or final:
        try:
            with st.spinner("Preparing your Word document…"):
                path = svc.build_report(workspace, final=final, pandoc=pandoc)
            st.success("Word document ready. Use the download button below.")
            st.session_state["export:" + workspace.name] = (str(path), sa.object_hash(sa.load(workspace)), sa.object_hash(config))
        except (ValueError, OSError) as exc:
            error(exc, workspace)
        except Exception:
            st.error("Word conversion failed. Check the Pandoc installation. Your review is saved; Markdown download remains available.")
    saved = st.session_state.get("export:" + workspace.name)
    if saved:
        path = Path(saved[0])
        if path.exists() and saved[1:] == (sa.object_hash(sa.load(workspace)), sa.object_hash(sa.read_json(workspace / "review.json"))):
            st.download_button("Download " + ("final" if "final" in path.stem else "draft") + " Word", path.read_bytes(), file_name=path.name, mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    with st.expander("Other downloads"):
        st.download_button("Download draft Markdown", body, file_name="review-draft.md", mime="text/markdown")


def main():
    if "next_screen" in st.session_state:
        st.session_state["screen"] = st.session_state.pop("next_screen")
    if "next_section" in st.session_state:
        st.session_state["section"] = st.session_state.pop("next_section")
    st.session_state.setdefault("screen", "Set up")
    found = svc.list_reviews()
    paths = [str(r["path"]) for r in found]
    active = st.session_state.get("workspace")
    with st.sidebar:
        st.title("Protocol Review")
        st.caption("Saved on this computer")
        options = [""] + paths
        names = {str(r["path"]): r["name"] + (" (legacy)" if r["legacy"] else "") for r in found}
        def switch():
            st.session_state["workspace"] = st.session_state["review_picker"] or None
            navigate("Set up")
            st.session_state.pop("source_id", None)
            st.session_state.pop("source_version", None)
            for stale in ("highlight", "pdf_page", "full_pdf"):
                st.session_state.pop(stale, None)
        if "review_picker" not in st.session_state:
            st.session_state["review_picker"] = active if active in paths else ""
        selected = st.selectbox("Saved review", options, format_func=lambda p: names.get(p, "New review"), key="review_picker", on_change=switch)
        if selected:
            st.session_state["workspace"] = selected
        st.radio("Workspace", SCREENS, key="screen")
    workspace = Path(st.session_state["workspace"]) if st.session_state.get("workspace") else None
    if workspace and not sa.active(workspace):
        st.info("This review uses the legacy workflow, which this app does not open. See legacy/README.md for its command-line tool, or choose New review for the guided app.")
        return
    if workspace:
        st.caption(sa.read_json(workspace / "review.json").get("ui_name", workspace.name))
    if st.session_state.get("notice"):
        st.success(st.session_state.pop("notice"))
    if st.session_state.get("edit_error"):
        st.error(st.session_state.pop("edit_error"))
    screen = st.session_state["screen"]
    if screen == "Set up":
        setup(workspace)
    elif workspace is None:
        st.info("Create or select a review to continue.")
        st.button("Set up a review →", on_click=navigate, args=("Set up",))
    elif screen == "Review workspace":
        review_workspace(workspace)
    else:
        export(workspace)


main()
