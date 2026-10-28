"""A local, guided workspace for statistical review memos."""
from pathlib import Path
import shutil
import sys

import streamlit as st
from streamlit_pdf_viewer import pdf_viewer

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
import stage_a as sa
import ui_service as svc

SCREENS = ["Set up", "Exchange with Elsa", "Review sections", "Export"]
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


def editor_key(workspace, item, kind):
    return f"{kind}:{workspace.name}:{item['key']}"


def save_item(workspace, item):
    svc.save_draft(workspace, item["key"], st.session_state[editor_key(workspace, item, "text")],
                   st.session_state[editor_key(workspace, item, "include")],
                   st.session_state[editor_key(workspace, item, "reason")], item["candidate_id"], item["manual"])


def on_edit(workspace, item):
    try:
        save_item(workspace, item)
    except (ValueError, OSError) as exc:
        st.session_state["edit_error"] = str(exc)


def choose_proposal(workspace, item, selector):
    try:
        svc.choose_candidate(workspace, item["key"], st.session_state[selector])
        for kind in ("text", "include", "reason"):
            st.session_state.pop(editor_key(workspace, item, kind), None)
    except (ValueError, OSError) as exc:
        st.session_state["edit_error"] = str(exc)


def source_click(version_key, page):
    st.session_state["source_version"] = version_key
    st.session_state["pdf_page"] = page or 1


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
                move("Review sections" if demo else "Set up", 3 if demo else None)
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
            notice("Documents saved. You can now prepare instructions for Elsa.")
            st.rerun()
        except (ValueError, OSError) as exc:
            error(exc, workspace)
    st.button("Next: exchange with Elsa →", on_click=navigate, args=("Exchange with Elsa",), disabled=not state["sources"])


def exchange(workspace):
    st.header("Exchange with Elsa")
    st.write("Get instructions here, use them in Elsa, then bring its response back to this screen.")
    state = sa.load(workspace)
    batch = st.selectbox("Information to extract", range(4), index=svc.recommended_batch(workspace),
                         format_func=lambda n: svc.BATCHES[n][0], key="batch:" + workspace.name)
    with st.expander("Choose individual fields (optional)"):
        eligible = {k: f for k, f in sa.fields(workspace).items() if f["mode"] not in {"manual", "group"}}
        selected = st.multiselect("Request only these fields instead", list(eligible),
                                  format_func=lambda k: eligible[k]["label"], key="fields:" + workspace.name)
    if st.button("Prepare instructions", type="primary"):
        try:
            request_id = svc.create_request(workspace, batch, ",".join(selected) if selected else None)
            st.session_state["request:" + workspace.name] = request_id
            notice("Instructions ready. Copy or download them below.")
            st.rerun()
        except (ValueError, OSError) as exc:
            error(exc, workspace)
    requests = list(reversed(state["requests"]))
    if requests:
        current = st.session_state.get("request:" + workspace.name)
        request_id = st.selectbox("Saved instructions", requests, index=requests.index(current) if current in requests else 0,
                                  format_func=lambda k: state["requests"][k]["created_at"][:16].replace("T", " ") + " · " + str(len(state["requests"][k]["fields"])) + " fields")
        manifest = state["requests"][request_id]
        instructions = (workspace / "stage_a/requests" / request_id / "instructions.md").read_text(encoding="utf-8")
        st.subheader("1. Take these instructions to Elsa")
        st.caption("The code box has a copy button in its upper-right corner. Attach the documents listed below in the same Elsa chat.")
        with st.expander("Copy instructions", expanded=True):
            st.code(instructions, language="markdown", height=220)
        st.download_button("Download instructions", instructions, file_name="elsa-instructions.md", mime="text/markdown")
        st.write("**Documents to attach in Elsa**")
        for source_id, meta in manifest["sources"].items():
            source = state["sources"].get(source_id)
            st.write("• " + meta["filename"])
            if source and sa.public_source(source) == meta and Path(source["path"]).is_file():
                st.download_button("Download " + meta["filename"], Path(source["path"]).read_bytes(), file_name=meta["filename"],
                                   key="docdl:" + source_id + request_id)
    else:
        st.info("Prepare instructions to start. Your PDFs must also be attached in Elsa.")
    st.subheader("2. Bring back Elsa’s JSON response")
    uploaded = st.file_uploader("Elsa response JSON", type=["json"], key="response:" + workspace.name)
    if st.button("Load response", disabled=uploaded is None):
        try:
            run_id, created = svc.import_bytes(workspace, uploaded.getvalue())
            new_state = sa.load(workspace)
            request_id = new_state["imports"][run_id]["request_id"]
            numbers = [v["section"] for v in new_state["requests"][request_id]["fields"].values()]
            notice("Response loaded. Review and approve its answers below." if created else "This response is already loaded. Your previous work is unchanged.")
            move("Review sections", min(numbers))
        except (ValueError, OSError) as exc:
            error(exc, workspace)


def source_panel(workspace):
    state = sa.load(workspace)
    sources = svc.source_versions(workspace)
    st.subheader("Source document")
    if not sources:
        st.info("Upload a document in Set up to view its pages here.")
        return
    if st.session_state.get("source_version") not in sources:
        st.session_state["source_version"] = next(iter(sources))
    source_id = st.selectbox("Document", list(sources), format_func=lambda k: sources[k]["filename"] + " · v" + sources[k]["version"] + (" (earlier version)" if not sources[k]["current"] else ""), key="source_version")
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
    if maximum and current > maximum:
        st.session_state["pdf_page"] = maximum
    else:
        st.session_state.setdefault("pdf_page", current)
    page = st.number_input("PDF page position", min_value=1, max_value=maximum, key="pdf_page")
    full = st.checkbox("Show full document", key="full_pdf")
    pdf_viewer(path.read_bytes(), height=720, key="pdf:" + workspace.name + source_id + source["sha256"][:12] + (":full" if full else ":" + str(page)),
               pages_to_render=[] if full else [page], render_text=True,
               scroll_to_page=page if full else None, zoom_level="auto")
    st.download_button("Download source PDF", path.read_bytes(), file_name=source["filename"], mime="application/pdf")


def review_sections(workspace):
    st.header("Review sections")
    st.caption("Edits save locally when you leave a text box. Saving does not approve an answer.")
    state = sa.load(workspace)
    statuses = svc.section_statuses(workspace)
    titles = {s["number"]: s["title"].rstrip(": ") for s in sa.catalog(workspace)["sections"]}
    if "section" not in st.session_state:
        st.session_state["section"] = 3
    number = st.selectbox("Section", list(titles), format_func=lambda n: f"{n}. {titles[n]} — {statuses[n]}", key="section")
    items = svc.section_items(workspace, number, state)
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        st.subheader(titles[number])
        with st.container(height=730):
            for item in items:
                st.markdown("#### " + item["label"])
                if item["missing"]:
                    st.info("This field needs extraction from Elsa.")
                    continue
                if len(item["proposals"]) > 1:
                    options = [p["id"] for p in reversed(item["proposals"])]
                    chosen = item["candidate_id"]
                    selector = editor_key(workspace, item, "proposal")
                    st.selectbox("Answer to use", options, index=options.index(chosen), key=selector,
                        format_func=lambda k: "Current accepted answer" if k == (item["accepted"] or {}).get("candidate_id") else "Proposal from " + state["candidates"][k]["imported_at"][:19].replace("T", " "),
                        on_change=choose_proposal, args=(workspace, item, selector))
                if item["candidate"]:
                    record = item["candidate"]["record"]
                    st.caption("Elsa: " + record["status"].replace("_", " ") + " · " + item["field"]["mode"])
                    if record["explanation"]:
                        st.write(record["explanation"])
                else:
                    st.caption("Your assessment — not extracted by Elsa")
                for kind, value in (("text", item["text"]), ("include", item["include"]), ("reason", item["reason"])):
                    st.session_state.setdefault(editor_key(workspace, item, kind), value)
                st.text_area("Memo wording", height=150, key=editor_key(workspace, item, "text"), on_change=on_edit, args=(workspace, item))
                st.checkbox("Include in memo", key=editor_key(workspace, item, "include"), on_change=on_edit, args=(workspace, item), disabled=bool(item["candidate"] and item["candidate"]["record"]["status"] == "not_applicable"))
                needs_reason = not st.session_state[editor_key(workspace, item, "include")] or bool(item["candidate"] and item["candidate"]["record"]["status"] != "found")
                st.text_input("Reason / disposition" + (" (required)" if needs_reason else " (optional)"), key=editor_key(workspace, item, "reason"), on_change=on_edit, args=(workspace, item))
                if item["candidate"]:
                    for index, source in enumerate(item["candidate"]["record"]["sources"]):
                        with st.expander("Evidence · " + (source["section"] or "Section unavailable"), expanded=True):
                            st.write(source["exact_excerpt"])
                            metadata = state["requests"][item["candidate"]["request_id"]]["sources"][source["document_id"]]
                            st.caption(f"Version: {metadata['version']} · PDF position: {source['pdf_page'] or 'unavailable'} · Printed label: {source['printed_page'] or 'unavailable'}")
                            st.button("View source", key=editor_key(workspace, item, "source") + str(index), on_click=source_click, args=(sa.object_hash(metadata), source["pdf_page"]))
                    with st.expander("Original proposal and search details"):
                        st.write(item["candidate"]["record"]["value"] or "No proposed value")
                        st.caption(item["candidate"]["search_scope"])
                st.divider()
        reviewer = sa.read_json(workspace / "review.json").get("ui_reviewer", "")
        save_col, approve_col = st.columns([1, 1.5])
        save_clicked = save_col.button("Save section draft")
        approve = approve_col.button("Approve section and continue →", type="primary", disabled=any(i["missing"] for i in items))
        if save_clicked or approve:
            try:
                for item in items:
                    if not item["missing"]:
                        save_item(workspace, item)
                if approve:
                    svc.approve_section(workspace, number, reviewer)
                    notice(titles[number] + " approved.")
                    screen, next_number, batch = svc.next_step(workspace)
                    st.session_state["batch:" + workspace.name] = batch
                    move(screen, next_number)
                notice("Section draft saved. It has not been approved.")
                st.rerun()
            except (ValueError, OSError) as exc:
                error(exc, workspace)
        if any(i["missing"] for i in items):
            st.button("Get instructions for Elsa →", on_click=navigate, args=("Exchange with Elsa",))
    with right:
        source_panel(workspace)


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
                    st.button("Review " + str(matched["section"]) + ": " + next(s["title"] for s in sa.catalog(workspace)["sections"] if s["number"] == matched["section"]), key="block:" + str(matched["section"]), on_click=navigate, args=("Review sections", matched["section"]))
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
            st.session_state.pop("section", None)
        if "review_picker" not in st.session_state:
            st.session_state["review_picker"] = active if active in paths else ""
        selected = st.selectbox("Saved review", options, format_func=lambda p: names.get(p, "New review"), key="review_picker", on_change=switch)
        if selected:
            st.session_state["workspace"] = selected
        st.radio("Workspace", SCREENS, key="screen")
    workspace = Path(st.session_state["workspace"]) if st.session_state.get("workspace") else None
    if workspace and not sa.active(workspace):
        st.info("This review uses the legacy workflow. It is unchanged and can still be used through the existing CLI. Choose New review for the guided app.")
        return
    if workspace:
        st.caption(sa.read_json(workspace / "review.json").get("ui_name", workspace.name))
        statuses = svc.section_statuses(workspace)
        done = sum(v == "Approved" for v in statuses.values())
        with st.sidebar:
            st.progress(done / 13, text=f"{done} of 13 sections approved")
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
    elif screen == "Exchange with Elsa":
        exchange(workspace)
    elif screen == "Review sections":
        review_sections(workspace)
    else:
        export(workspace)


main()
