"""Local application services shared by Streamlit and its tests (no Streamlit imports)."""
import contextlib
import copy
import io
import os
from pathlib import Path
import re
import shutil
import threading
from types import SimpleNamespace
import uuid

import demo_stage_a
import review
import stage_a as sa

ROOT = Path(__file__).resolve().parents[1]
BATCHES = [("Objectives, design and endpoints", "3,4,5"),
           ("Hypotheses and analyses", "6,7,8"),
           ("Background, interim plans and sample size", "2,9,10"),
           ("Factual executive summary", "1")]
_LOCK = threading.RLock()


def quiet(function, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return function(*args, **kwargs)


def reviews_root():
    return Path(os.environ.get("XYZ_REVIEWS_DIR", ROOT / "reviews")).resolve()


def list_reviews():
    root = reviews_root()
    if not root.exists():
        return []
    found = []
    for path in sorted(root.iterdir()):
        if not (path / "review.json").is_file():
            continue
        try:
            config = sa.read_json(path / "review.json")
            found.append(dict(path=path, name=config.get("ui_name") or config.get("submission") or path.name,
                              legacy=config.get("workflow") != "stage-a"))
        except (ValueError, OSError):
            continue
    return found


def create_review(name, reviewer, demo=False):
    if not name.strip() or not reviewer.strip():
        raise ValueError("Enter a review name and your name.")
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48] or "review"
    path = reviews_root() / (slug + "-" + uuid.uuid4().hex[:8])
    if demo:
        quiet(demo_stage_a.create, path)
    else:
        quiet(review.initialize, path, "stage-a")
    config = sa.read_json(path / "review.json")
    config.update(ui_name=name.strip(), ui_reviewer=reviewer.strip(), submission=name.strip())
    sa.write_json(path / "review.json", config)
    return path


def update_metadata(workspace, name, reviewer, author, date):
    if not name.strip() or not reviewer.strip():
        raise ValueError("Enter a review name and reviewer name.")
    config = sa.read_json(workspace / "review.json")
    config.update(ui_name=name.strip(), submission=name.strip(), ui_reviewer=reviewer.strip(), author=author, date=date)
    sa.write_json(workspace / "review.json", config)


def store_source(workspace, filename, data, role, version="unknown", date="unknown", replace_id=None):
    if not data or b"%PDF-" not in data[:1024]:
        raise ValueError("Choose a PDF document. This file does not have a PDF header.")
    name = Path(filename.replace("\\", "/")).name
    name = re.sub(r'[^A-Za-z0-9._ -]', '_', name).strip(". ") or "document.pdf"
    with _LOCK:
        state = sa.load(workspace)
        if role == "protocol":
            identifier = "PROTOCOL"
        else:
            if not replace_id:
                for existing_id, source in state["sources"].items():
                    if source["role"] == "background" and source["filename"] == name and source["sha256"] == sa.digest(data) and source["version"] == (version or "unknown") and source["date"] == (date or "unknown"):
                        return existing_id
            identifier = replace_id or ("BACKGROUND_" + uuid.uuid4().hex[:8])
        fingerprint = sa.digest(data)
        old = state["sources"].get(identifier)
        if old and all(old[k] == v for k, v in dict(sha256=fingerprint, version=version or "unknown", date=date or "unknown").items()):
            return identifier
        path = workspace / "inputs" / identifier / fingerprint[:16] / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(data)
        quiet(sa.register_source, workspace, path, identifier, role, version or "unknown", date or "unknown")
        return identifier


def source_versions(workspace):
    """Keep evidence attached to its original source version after a replacement."""
    state = sa.load(workspace)
    versions = {}
    for identifier, source in state["sources"].items():
        versions[sa.object_hash(sa.public_source(source))] = dict(source, id=identifier, current=True)
    for manifest in reversed(list(state["requests"].values())):
        for identifier, meta in manifest["sources"].items():
            version_key = sa.object_hash(meta)
            if version_key not in versions:
                path = workspace / "inputs" / identifier / meta["sha256"][:16] / meta["filename"]
                versions[version_key] = dict(meta, path=str(path), current=False)
    return versions


def import_bytes(workspace, data):
    """Deduplicate browser retries without changing the CLI's deliberate reimport behavior."""
    with _LOCK:
        state = sa.load(workspace)
        fingerprint = sa.digest(data)
        for run_id, run in state["imports"].items():
            if run["sha256"] == fingerprint:
                if sa.provenance_problems(workspace, state):
                    raise ValueError("A saved import is missing or changed. Restore its archived files before continuing.")
                return run_id, False
        path = workspace / "stage_a/uploads" / (fingerprint + ".json")
        # Validate prior to saving uploads, including the unknown-request check.
        payload = sa.strict_json(data.decode("utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("request_id"), str) or payload["request_id"] not in state["requests"]:
            raise ValueError("This response does not match a request in this review. Upload the response for instructions created here.")
        sa.validate_response(payload, state["requests"][payload["request_id"]])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        # Core importer intentionally reads UTF-8; reject BOMs without silently changing provenance.
        return quiet(sa.import_response, workspace, path), True


def create_request(workspace, batch, custom_fields=None):
    with _LOCK:
        state = sa.load(workspace)
        selection = BATCHES[batch][1]
        chosen = custom_fields or ("EXECUTIVE.FACTS" if batch == 3 else None)
        # Reuse the latest unchanged request; repeated button clicks are harmless.
        for request_id, manifest in reversed(list(state["requests"].items())):
            if manifest.get("ui_batch") == batch and manifest.get("ui_custom_fields") == chosen:
                sources = {k: sa.public_source(v) for k, v in state["sources"].items()}
                if manifest["sources"] == sources and manifest["entities"] == sa.entity_registry(state) and (
                    not manifest["summary_dependencies"] or manifest["summary_dependencies"] == sa.facts_hash(state)
                ):
                    return request_id
        request_id = quiet(sa.prepare, workspace, selection, chosen)
        state = sa.load(workspace)
        manifest = state["requests"][request_id]
        manifest.update(ui_batch=batch, ui_custom_fields=chosen)
        sa.save(workspace, state)
        sa.write_json(workspace / "stage_a/requests" / request_id / "manifest.json", manifest)
        return request_id


def section_items(workspace, number, state=None):
    state = state or sa.load(workspace)
    items = []
    registry = sa.entity_registry(state)
    for field in sa.fields(workspace).values():
        if field["section"] != number or field["mode"] == "group":
            continue
        identifier = field["id"]
        groups = {}
        for candidate in state["candidates"].values():
            if candidate["field_id"] == identifier:
                groups.setdefault(candidate["record"]["instance_id"], []).append(candidate)
        instances = list(groups)
        instances += [k.split("/", 1)[1] for k in state["reviewed"] if k.startswith(identifier + "/") and k.split("/", 1)[1] not in instances]
        if field["scope"] == "study":
            instances = ["study"]
        else:
            instances += [e["id"] for e in registry.values() if e["kind"] == field["scope"] and e["id"] not in instances]
        if not instances:
            instances = ["none"]
        for instance in instances:
            item_key = sa.key(identifier, instance)
            accepted = state["reviewed"].get(item_key)
            proposals = groups.get(instance, [])
            draft = state.get("ui_drafts", {}).get(item_key)
            candidate_id = (draft["candidate_id"] if draft else accepted["candidate_id"] if accepted else proposals[-1]["id"] if proposals else None)
            candidate = state["candidates"].get(candidate_id)
            manual = field["mode"] == "manual"
            if draft:
                text, include, reason = draft["text"], draft["include"], draft["reason"]
            elif accepted:
                path = workspace / accepted["edit_path"]
                text = path.read_text(encoding="utf-8").strip() if path.exists() else accepted["text"]
                include, reason = accepted["include"], accepted["reason"]
            elif manual:
                text = (workspace / "stage_a/manual" / (identifier + ".txt")).read_text(encoding="utf-8").strip()
                text = "" if text.startswith("[[") else text
                include, reason = True, ""
            elif candidate:
                path = sa.candidate_path(workspace, candidate_id)
                text = path.read_text(encoding="utf-8").strip() if path.exists() else candidate["record"]["value"] or sa.DISPOSITIONS[candidate["record"]["status"]]
                include, reason = candidate["record"]["status"] != "not_applicable", ""
            else:
                text, include, reason = "", True, ""
            entity = registry.get(instance) or (candidate or {}).get("entity")
            items.append(dict(key=item_key, field=field, manual=manual, missing=not manual and not candidate,
                              label=field["label"] + (" — " + entity["label"] if entity else ""),
                              candidate_id=candidate_id, candidate=candidate, proposals=proposals, accepted=accepted,
                              text=text, include=include, reason=reason))
    return items


def save_draft(workspace, item_key, text, include, reason, candidate_id, manual=False):
    with _LOCK:
        state = sa.load(workspace)
        identifier, instance = item_key.split("/", 1)
        spec = sa.fields(workspace).get(identifier)
        if not spec or spec["mode"] == "group":
            raise ValueError("Unknown review field")
        if manual:
            if spec["mode"] != "manual" or instance != "study" or candidate_id is not None:
                raise ValueError("Invalid manual field")
        else:
            candidate = state["candidates"].get(candidate_id)
            if not candidate or sa.key(candidate["field_id"], candidate["record"]["instance_id"]) != item_key:
                raise ValueError("Proposal does not belong to this field")
        state.setdefault("ui_drafts", {})[item_key] = dict(candidate_id=candidate_id, manual=manual,
                                                         text=text.strip(), include=bool(include), reason=reason.strip())
        sa.save(workspace, state)


def choose_candidate(workspace, item_key, candidate_id):
    state = sa.load(workspace)
    accepted = state["reviewed"].get(item_key)
    if accepted and accepted["candidate_id"] == candidate_id:
        text, include, reason = accepted["text"], accepted["include"], accepted["reason"]
    else:
        candidate = state["candidates"][candidate_id]
        record = candidate["record"]
        text = record["value"] or sa.DISPOSITIONS[record["status"]]
        include, reason = record["status"] != "not_applicable", ""
    save_draft(workspace, item_key, text, include, reason, candidate_id)


def approve_section(workspace, number, reviewer):
    """Validate all displayed decisions, then commit edit files and one state update."""
    with _LOCK:
        state = sa.load(workspace)
        items = section_items(workspace, number, state)
        updated = copy.deepcopy(state)
        writes = []
        for item in items:
            if item["missing"]:
                raise ValueError(f"{item['label']}: extract this information before approving the section.")
            old = item["accepted"]
            if old and all(item[k] == old[k] for k in ("candidate_id", "text", "include", "reason")) and not sa.stale_reasons(workspace, state, old):
                updated.get("ui_drafts", {}).pop(item["key"], None)
                continue
            try:
                result = sa.apply_review_decision(workspace, updated, candidate_id=item["candidate_id"],
                    manual=item["field"]["id"] if item["manual"] else None, reviewer=reviewer,
                    text=item["text"], reason=item["reason"], exclude=not item["include"])
            except ValueError as exc:
                raise ValueError(f"{item['label']}: {exc}") from exc
            if result:
                writes.append(result)
            updated.get("ui_drafts", {}).pop(item["key"], None)
        backups = {p: p.read_bytes() if p.exists() else None for p, data in writes}
        try:
            for path, data in writes:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            sa.save(workspace, updated)
        except OSError:
            for path, data in backups.items():
                if data is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(data)
            raise


def section_statuses(workspace):
    state = sa.load(workspace)
    result = {}
    for section in sa.catalog(workspace)["sections"]:
        items = section_items(workspace, section["number"], state)
        if any(item["missing"] for item in items):
            status = "Needs extraction"
        elif all(item["accepted"] and not sa.stale_reasons(workspace, state, item["accepted"]) and
                 all(item[k] == item["accepted"][k] for k in ("candidate_id", "text", "include", "reason")) for item in items):
            status = "Approved"
        else:
            status = "Needs review"
        result[section["number"]] = status
    return result


def recommended_batch(workspace):
    statuses = section_statuses(workspace)
    for batch, (_, sections) in enumerate(BATCHES):
        if any(statuses[int(n)] != "Approved" for n in sections.split(",")):
            return batch
    return 3


def next_step(workspace):
    statuses = section_statuses(workspace)
    for batch, numbers in enumerate(((3, 4, 5), (6, 7, 8), (2, 9, 10), (1,), (11, 12, 13))):
        pending = [n for n in numbers if statuses[n] != "Approved"]
        if not pending:
            continue
        reviewable = [n for n in pending if statuses[n] == "Needs review"]
        if reviewable:
            return "Review sections", reviewable[0], min(batch, 3)
        return "Exchange with Elsa", pending[0], min(batch, 3)
    return "Export", None, 3


def build_report(workspace, final=False, word=True, pandoc=None):
    out = workspace / "exports" / ("review-final" if final else "review-draft")
    output = out.with_suffix(".docx" if word else ".md")
    args = SimpleNamespace(workspace=workspace, output=output, final=final, reviewer_approved=final,
                           acknowledge_unresolved=False, pandoc=pandoc or "pandoc", reference_doc=None)
    quiet(review.build, args)
    return output


def friendly_error(error, workspace=None):
    text = str(error)
    if workspace:
        for identifier, field in sa.fields(workspace).items():
            text = text.replace(identifier, field["label"])
    text = re.sub(r"\$\.fields\.", "Response field: ", text)
    text = text.replace("missing keys:", "Missing information:")
    if "definitions/inventory first" in text:
        return "Approve the endpoint definitions in Review sections before requesting their analyses."
    if "factual fields before summary" in text:
        return "Finish reviewing the factual sections before generating the executive summary."
    return text
