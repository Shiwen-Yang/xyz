"""Offline Elsa requests, fixed-contract validation, provenance, review, and rendering.

Only the Python standard library is needed. This module never calls Elsa or a network service.
"""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "review_template/stage_a"
ID = r"^[A-Za-z][A-Za-z0-9_-]{0,63}$"
STATUSES = ["found", "not_found", "not_applicable", "conflicting", "unreadable"]
KINDS = ["primary_objective", "secondary_objective", "primary_endpoint", "secondary_endpoint",
         "experimental_arm", "control_arm", "interim_look"]
DISPOSITIONS = {"not_found": "Not located in supplied sources.",
                "not_applicable": "Not applicable.", "conflicting": "Conflicting source statements; reviewer disposition required.",
                "unreadable": "Source material could not be read; reviewer disposition required."}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def object_hash(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"Non-JSON numeric constant: {value}")
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid_constant)


def read_json(path):
    return strict_json(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    # Same-directory replacement avoids truncated review state on interrupted writes.
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        stream.write(text)
        temporary = Path(stream.name)
    temporary.replace(path)


def active(workspace):
    return read_json(workspace / "review.json").get("workflow") == "stage-a"


def load(workspace):
    state = read_json(workspace / "stage_a/state.json")
    if state["workflow_version"] != 1:
        raise ValueError("Unsupported Stage A workflow version")
    return state


def save(workspace, state):
    write_json(workspace / "stage_a/state.json", state)


def catalog(workspace):
    data = read_json(workspace / "stage_a/catalog.json")
    if data["catalog_version"] != 1:
        raise ValueError("Unsupported Stage A catalog version")
    return data


def fields(workspace):
    return {f["id"]: dict(f, section=s["number"]) for s in catalog(workspace)["sections"] for f in s["fields"]}


def initialize(workspace):
    directory = workspace / "stage_a"
    directory.mkdir()
    shutil.copyfile(ASSETS / "catalog.json", directory / "catalog.json")
    state = dict(workflow_version=1, catalog_version=1, sources={}, requests={}, imports={},
                 candidates={}, decisions={}, reviewed={}, history=[])
    save(workspace, state)
    for field in fields(workspace).values():
        if field["mode"] == "manual":
            path = directory / "manual" / (field["id"] + ".txt")
            path.parent.mkdir(exist_ok=True)
            path.write_text("[[" + field["id"] + "]]\n", encoding="utf-8")


def public_source(source):
    return {k: v for k, v in source.items() if k != "path"}


def register_source(workspace, path, identifier, role, version, date, pages=None):
    if not re.fullmatch(ID, identifier) or identifier in {"study", "none"}:
        raise ValueError("Source ID must be a safe identifier other than study/none")
    if role not in {"protocol", "background"}:
        raise ValueError("Source role must be protocol or background")
    if not version.strip() or not date.strip():
        raise ValueError("Supply source version and date (use 'unknown' explicitly if unavailable)")
    if pages is not None and (type(pages) is not int or pages < 1):
        raise ValueError("Page count must be a positive integer")
    state = load(workspace)
    path = path.resolve()
    state["sources"][identifier] = dict(id=identifier, filename=path.name, path=str(path), role=role,
                                         version=version, date=date, pdf_pages=pages,
                                         sha256=file_hash(path))
    state["history"].append(dict(action="register_source", source_id=identifier, at=now()))
    save(workspace, state)
    print(f"Registered {identifier}: {path.name} ({role}, {version})")


def source_problems(state):
    problems = []
    for identifier, source in state["sources"].items():
        path = Path(source["path"])
        if not path.is_file():
            problems.append(f"Source {identifier} is unavailable at its registered path")
        elif file_hash(path) != source["sha256"]:
            problems.append(f"Source {identifier} changed; register its current version before proceeding")
    return problems


def entity_registry(state):
    entities = {}
    for reviewed in state["reviewed"].values():
        if reviewed["candidate_id"]:
            candidate = state["candidates"][reviewed["candidate_id"]]
            entity = candidate["entity"]
            if entity and candidate["record"]["status"] == "found":
                if entity["id"] in entities and entities[entity["id"]] != entity:
                    raise ValueError(f"Conflicting accepted entity identity: {entity['id']}")
                entities[entity["id"]] = entity
    return entities


def key(field_id, instance_id):
    return field_id + "/" + instance_id


def accepted_facts(state):
    return {k: v for k, v in state["reviewed"].items()
            if v["candidate_id"] and not k.startswith("EXECUTIVE.")}


def facts_hash(state):
    return object_hash(dict(facts=accepted_facts(state), sources={k: public_source(v) for k, v in state["sources"].items()}))


def schema_for(manifest):
    """Generate a JSON Schema and use the same document for local validation."""
    string = {"type": "string"}
    entity = {"type": "object", "additionalProperties": False,
              "required": ["id", "kind", "label"], "properties": {
                  "id": dict(string, pattern=ID), "kind": dict(string, enum=KINDS),
                  "label": dict(string, minLength=1)}}
    source = {"type": "object", "additionalProperties": False,
              "required": ["document_id", "pdf_page", "printed_page", "section", "exact_excerpt"],
              "properties": {"document_id": dict(string, enum=list(manifest["sources"])),
                             "pdf_page": {"type": ["integer", "null"], "minimum": 1},
                             "printed_page": {"type": ["string", "null"]},
                             "section": {"type": ["string", "null"]},
                             "exact_excerpt": dict(string, minLength=1)}}
    record = {"type": "object", "additionalProperties": False,
              "required": ["instance_id", "status", "value", "sources", "explanation"],
              "properties": {"instance_id": dict(string, pattern=ID),
                             "status": dict(string, enum=STATUSES),
                             "value": {"type": ["string", "null"]},
                             "sources": {"type": "array", "items": source},
                             "explanation": string}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
            "$defs": {"record": record},
            "additionalProperties": False,
            "required": ["schema_version", "catalog_version", "request_id", "search_scope", "entities", "fields"],
            "properties": {"schema_version": {"type": "integer", "const": 1},
                           "catalog_version": {"type": "integer", "const": manifest["catalog_version"]},
                           "request_id": dict(string, const=manifest["request_id"]),
                           "search_scope": dict(string, minLength=1),
                           "entities": {"type": "array", "items": entity},
                           "fields": {"type": "object", "additionalProperties": False,
                                      "required": list(manifest["fields"]),
                                      "properties": {identifier: {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/record"}}
                                                     for identifier in manifest["fields"]}}}}


def validate_schema(value, schema, location="$", definitions=None):
    """Validate the finite JSON-Schema vocabulary emitted above, not arbitrary schemas."""
    definitions = schema.get("$defs", {}) if definitions is None else definitions
    if "$ref" in schema:
        reference = schema["$ref"]
        if not reference.startswith("#/$defs/") or reference[len("#/$defs/"):] not in definitions:
            raise ValueError("Unsupported reference in generated response schema")
        return validate_schema(value, definitions[reference[len("#/$defs/"):]], location, definitions)
    types = {"object": dict, "array": list, "string": str, "integer": int, "null": type(None)}
    expected = schema.get("type")
    if expected:
        expected = [expected] if isinstance(expected, str) else expected
        if not any(type(value) is types[t] for t in expected):
            raise ValueError(f"{location}: expected {' or '.join(expected)}")
    if "const" in schema and value != schema["const"]:
        raise ValueError(f"{location}: unexpected value (request/catalog mismatch)")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{location}: value is not in the allowed set")
    if isinstance(value, dict):
        missing = set(schema.get("required", [])) - set(value)
        if missing:
            raise ValueError(f"{location}: missing keys: {', '.join(sorted(missing))}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False and set(value) - set(props):
            raise ValueError(f"{location}: unexpected keys: {', '.join(sorted(set(value) - set(props)))}")
        for name, child in value.items():
            if name in props:
                validate_schema(child, props[name], location + "." + name, definitions)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ValueError(f"{location}: too few items")
        for index, child in enumerate(value):
            validate_schema(child, schema.get("items", {}), f"{location}[{index}]", definitions)
    if isinstance(value, str):
        if len(value.strip()) < schema.get("minLength", 0):
            raise ValueError(f"{location}: blank/short string")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            raise ValueError(f"{location}: invalid identifier")
    if type(value) is int and value < schema.get("minimum", value):
        raise ValueError(f"{location}: integer is below minimum")


def prepare(workspace, selection, field_selection=None, source_selection=None):
    state = load(workspace)
    problems = source_problems(state)
    if problems:
        raise ValueError("\n".join(problems))
    sources = state["sources"]
    if source_selection:
        requested_sources = {s.strip() for s in source_selection.split(",")}
        if not requested_sources <= sources.keys():
            raise ValueError("Unknown requested source ID")
        sources = {k: v for k, v in sources.items() if k in requested_sources}
    if sum(s["role"] == "protocol" for s in sources.values()) != 1:
        raise ValueError("A request needs exactly one current protocol source; register sources first")
    entries = fields(workspace)
    if field_selection:
        selected = [v.strip() for v in field_selection.split(",")]
        if not selected or not set(selected) <= entries.keys():
            raise ValueError("Unknown or empty field selection")
    else:
        if selection == "all":
            section_numbers = set(range(2, 11))
        else:
            try:
                section_numbers = {int(v) for v in selection.split(",")}
            except ValueError as exc:
                raise ValueError("Sections must be comma-separated numbers") from exc
            if not section_numbers or not section_numbers <= set(range(1, 14)):
                raise ValueError("Sections must be between 1 and 13")
        selected = [f["id"] for f in entries.values() if f["section"] in section_numbers and f["mode"] not in {"manual", "group"}]
    if not selected or any(entries[f]["mode"] in {"manual", "group"} for f in selected):
        raise ValueError("Select extractable fields, not manual fields or grouping labels")
    if "EXECUTIVE.FACTS" in selected and len(selected) != 1:
        raise ValueError("Prepare EXECUTIVE.FACTS separately after accepting the factual fields")
    registry = entity_registry(state)
    discovery_scopes = {entries[f]["scope"] for f in selected if entries[f]["discovers_entities"]}
    manifest_fields = {}
    for identifier in selected:
        field = copy.deepcopy(entries[identifier])
        field.pop("depth", None)
        field.pop("group", None)
        scope = field["scope"]
        instances = [e["id"] for e in registry.values() if e["kind"] == scope]
        if scope == "study":
            instances = ["study"]
        elif not field["discovers_entities"] and not instances and scope not in discovery_scopes:
            inventory = {"primary_endpoint": "ENDPOINTS.PRIMARY", "secondary_endpoint": "ENDPOINTS.SECONDARY", "interim_look": "INTERIM.METHOD"}.get(scope)
            disposition = state["reviewed"].get(key(inventory, "none"))
            if disposition:
                instances = ["none"]
            else:
                raise ValueError(f"{identifier}: accept the {scope} definitions/inventory first")
        field["expected_instances"] = instances
        manifest_fields[identifier] = field
    request_id = "q_" + uuid.uuid4().hex[:16]
    manifest = dict(schema_version=1, catalog_version=1, request_id=request_id, created_at=now(),
                    sources={k: public_source(v) for k, v in sources.items()},
                    entities=registry, fields=manifest_fields, summary_dependencies=None)
    if selected == ["EXECUTIVE.FACTS"]:
        blockers = readiness(workspace, state, check_summary=False, check_manual=False)
        if blockers:
            raise ValueError("Accept/dispose of the factual fields before summary drafting:\n" + "\n".join(blockers))
        manifest["summary_dependencies"] = facts_hash(state)
        manifest["accepted_facts"] = {
            k: dict(value=v["text"], included=True,
                    status=state["candidates"][v["candidate_id"]]["record"]["status"],
                    sources=state["candidates"][v["candidate_id"]]["record"]["sources"])
            for k, v in accepted_facts(state).items() if v["include"]}
    schema = schema_for(manifest)
    directory = workspace / "stage_a/requests" / request_id
    directory.mkdir(parents=True)
    write_json(directory / "manifest.json", manifest)
    write_json(directory / "response.schema.json", schema)
    prompt = (ASSETS / "instructions.md").read_text(encoding="utf-8")
    prompt += "\n\n## This request\n\n```json\n" + json.dumps(manifest, ensure_ascii=False, indent=2) + "\n```\n"
    prompt += "\n## Required response schema\n\n```json\n" + json.dumps(schema, ensure_ascii=False, indent=2) + "\n```\n"
    (directory / "instructions.md").write_text(prompt, encoding="utf-8")
    state["requests"][request_id] = manifest
    save(workspace, state)
    print(f"Prepared {request_id}: upload {directory / 'instructions.md'} and the listed documents to Elsa")
    return request_id


def validate_response(payload, manifest):
    validate_schema(payload, schema_for(manifest))
    entities = {}
    registry = manifest["entities"]
    for entity in payload["entities"]:
        identifier = entity["id"]
        if identifier in {"study", "none"} or identifier in entities:
            raise ValueError("Duplicate or reserved entity ID")
        if identifier in registry and entity != registry[identifier]:
            raise ValueError(f"Entity {identifier} would redefine an accepted identity")
        entities[identifier] = entity
    available = dict(registry, **entities)
    used_new = set()
    discovery_scopes = {f["scope"] for f in manifest["fields"].values() if f["discovers_entities"]}
    for identifier, records in payload["fields"].items():
        spec = manifest["fields"][identifier]
        seen = set()
        for record in records:
            instance = record["instance_id"]
            if instance in seen:
                raise ValueError(f"{identifier}: duplicate instance {instance}")
            seen.add(instance)
            if spec["scope"] == "study":
                if instance != "study":
                    raise ValueError(f"{identifier}: singleton instance must be study")
            elif instance == "none":
                if record["status"] == "found" or len(records) != 1 or (spec["expected_instances"] and spec["expected_instances"] != ["none"]):
                    raise ValueError(f"{identifier}: none cannot replace existing entities or a found fact")
            else:
                if instance not in available or available[instance]["kind"] != spec["scope"]:
                    raise ValueError(f"{identifier}: wrong or missing entity for {instance}")
                if instance not in registry:
                    if spec["scope"] not in discovery_scopes:
                        raise ValueError(f"{identifier}: cannot invent an endpoint/arm/look identity")
                    if spec["discovers_entities"]:
                        if record["status"] != "found":
                            raise ValueError("New entities require a found definition/inventory record; otherwise use none")
                        used_new.add(instance)
            status = record["status"]
            if status == "found":
                if not isinstance(record["value"], str) or not record["value"].strip() or not record["sources"]:
                    raise ValueError(f"{identifier}: found requires nonempty text and evidence")
                if spec["mode"] == "verbatim":
                    quotation = " ".join(record["value"].split())
                    excerpts = " ".join(" ".join(s["exact_excerpt"].split()) for s in record["sources"])
                    if quotation not in excerpts:
                        raise ValueError(f"{identifier}: verbatim value does not match its returned excerpts (whitespace ignored)")
            else:
                if record["value"] is not None or not record["explanation"].strip():
                    raise ValueError(f"{identifier}: unresolved/inapplicable results require null value and explanation")
                if status == "not_applicable" and not record["sources"]:
                    raise ValueError(f"{identifier}: proposed inapplicability requires evidence")
                if status == "conflicting" and len({object_hash(s) for s in record["sources"]}) < 2:
                    raise ValueError(f"{identifier}: conflict requires competing source passages")
            for source in record["sources"]:
                maximum = manifest["sources"][source["document_id"]]["pdf_pages"]
                if maximum is not None and source["pdf_page"] is not None and source["pdf_page"] > maximum:
                    raise ValueError(f"{identifier}: PDF page exceeds registered document page count")
            if status in {"found", "not_applicable"} and spec["source_scope"] == "protocol" and not manifest["summary_dependencies"]:
                if not any(manifest["sources"][s["document_id"]]["role"] == "protocol" for s in record["sources"]):
                    raise ValueError(f"{identifier}: protocol-scoped facts require protocol evidence")
            if manifest["summary_dependencies"]:
                allowed = [s for fact in manifest["accepted_facts"].values() for s in fact["sources"]]
                if any(s not in allowed for s in record["sources"]):
                    raise ValueError("Summary evidence must come from the supplied accepted facts")
        if spec["scope"] == "study" and len(records) != 1:
            raise ValueError(f"{identifier}: singleton field has multiple records")
        if not set(spec["expected_instances"]) <= seen:
            raise ValueError(f"{identifier}: missing requested instances")
        if not spec["discovers_entities"] and spec["expected_instances"] and seen != set(spec["expected_instances"]):
            raise ValueError(f"{identifier}: unexpected instances")
    if (set(entities) - set(registry)) != used_new:
        raise ValueError("Every new entity must be used by an entity-discovery field")
    for identifier, records in payload["fields"].items():
        spec = manifest["fields"][identifier]
        if not spec["discovers_entities"] and spec["scope"] in discovery_scopes:
            expected = {e["id"] for e in available.values() if e["kind"] == spec["scope"]}
            if expected and {r["instance_id"] for r in records} != expected:
                raise ValueError(f"{identifier}: each discovered entity needs its own result")


def import_response(workspace, path):
    state = load(workspace)
    raw = path.read_bytes()
    payload = strict_json(raw.decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("request_id"), str) or payload["request_id"] not in state["requests"]:
        raise ValueError("Unknown or missing request ID")
    manifest = state["requests"][payload["request_id"]]
    validate_response(payload, manifest)
    for identifier, source in manifest["sources"].items():
        current = state["sources"].get(identifier)
        if current is None or public_source(current) != source:
            raise ValueError("Source registry changed since request preparation; prepare a new request")
    problems = source_problems(state)
    if problems:
        raise ValueError("\n".join(problems))
    run_id = "run_" + uuid.uuid4().hex[:16]
    candidates = {}
    for identifier, records in payload["fields"].items():
        for record in records:
            candidate_id = "c_" + uuid.uuid4().hex[:16]
            entity = next((e for e in payload["entities"] if e["id"] == record["instance_id"]),
                          manifest["entities"].get(record["instance_id"]))
            candidates[candidate_id] = dict(id=candidate_id, run_id=run_id, request_id=manifest["request_id"],
                                            field_id=identifier, entity=entity, record=copy.deepcopy(record),
                                            search_scope=payload["search_scope"], imported_at=now())
    directory = workspace / "stage_a/imports" / run_id
    directory.mkdir(parents=True)
    (directory / "original.json").write_bytes(raw)
    write_json(directory / "candidates.json", candidates)
    state["imports"][run_id] = dict(request_id=manifest["request_id"], sha256=digest(raw),
                                     candidates_sha256=digest((directory / "candidates.json").read_bytes()),
                                     imported_at=now())
    state["candidates"].update(candidates)
    save(workspace, state)
    print(f"Imported {run_id}: {len(candidates)} candidates; reviewed text was not changed")
    return run_id


def provenance_problems(workspace, state):
    problems = []
    for run_id, run in state["imports"].items():
        for name, expected in (("original.json", run["sha256"]), ("candidates.json", run["candidates_sha256"])):
            path = workspace / "stage_a/imports" / run_id / name
            if not path.is_file() or digest(path.read_bytes()) != expected:
                problems.append(f"Provenance file changed or missing: {run_id}/{name}")
    return problems


def candidate_path(workspace, candidate_id):
    return workspace / "stage_a/edits" / (candidate_id + ".txt")


def ensure_edit_file(workspace, candidate):
    path = candidate_path(workspace, candidate["id"])
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        record = candidate["record"]
        path.write_text((record["value"] if record["status"] == "found" else DISPOSITIONS[record["status"]]) + "\n", encoding="utf-8")
    return path


def stale_reasons(workspace, state, reviewed):
    reasons = []
    path = workspace / reviewed["edit_path"]
    if not path.exists() or digest(path.read_bytes()) != reviewed["edit_sha256"]:
        reasons.append("edited text has unapproved changes")
    if reviewed["candidate_id"]:
        candidate = state["candidates"][reviewed["candidate_id"]]
        manifest = state["requests"][candidate["request_id"]]
        for identifier, source in manifest["sources"].items():
            if identifier not in state["sources"] or public_source(state["sources"][identifier]) != source:
                reasons.append("source version/metadata changed")
                break
        if manifest["summary_dependencies"] and manifest["summary_dependencies"] != facts_hash(state):
            reasons.append("summary facts changed; prepare and review a new summary")
    return reasons


def review_item(workspace, candidate_id=None, manual=None, action=None, reviewer=None, reason="", exclude=False):
    state = load(workspace)
    if not action:
        if candidate_id or manual or reviewer or reason or exclude:
            raise ValueError("Supply --accept or --reject for a field decision; bare review generates the report")
        return verification_report(workspace)
    apply_review_decision(workspace, state, candidate_id, manual, action, reviewer, reason, exclude)
    save(workspace, state)
    print(f"Decision recorded; reviewer: {reviewer}")
    return verification_report(workspace)


def apply_review_decision(workspace, state, candidate_id=None, manual=None, action="accept",
                          reviewer=None, reason="", exclude=False, text=None):
    """Validate/apply one decision in memory; caller commits state atomically.

    With explicit text, return the canonical edit file and bytes to commit. The UI
    can validate an entire section before writing any approvals or edit files.
    The CLI retains its existing on-disk edit-file behavior when text is None.
    """
    explicit_text = text is not None
    if action not in {"accept", "reject"}:
        raise ValueError("Decision must be accept or reject")
    if not reviewer or not reviewer.strip():
        raise ValueError("Supply --reviewer for an explicit decision")
    if bool(candidate_id) == bool(manual):
        raise ValueError("Select exactly one --candidate or --manual field")
    problems = provenance_problems(workspace, state)
    if problems:
        raise ValueError("\n".join(problems))
    candidate = None
    if candidate_id:
        if candidate_id not in state["candidates"]:
            raise ValueError("Unknown candidate ID")
        candidate = state["candidates"][candidate_id]
        identifier = candidate["field_id"]
        instance = candidate["record"]["instance_id"]
        path = candidate_path(workspace, candidate_id) if explicit_text else ensure_edit_file(workspace, candidate)
        requires_reason = exclude or candidate["record"]["status"] != "found"
        manifest = state["requests"][candidate["request_id"]]
        if action == "accept":
            if any(k not in state["sources"] or public_source(state["sources"][k]) != v for k, v in manifest["sources"].items()):
                raise ValueError("Candidate uses outdated sources; prepare a fresh request")
            if manifest["summary_dependencies"] and manifest["summary_dependencies"] != facts_hash(state):
                raise ValueError("Summary is based on outdated facts; prepare a fresh request")
            if candidate["entity"]:
                existing = entity_registry(state).get(instance)
                if existing and existing != candidate["entity"]:
                    raise ValueError("Candidate would redefine an accepted entity identity")
    else:
        spec = fields(workspace).get(manual)
        if not spec or spec["mode"] != "manual":
            raise ValueError("Unknown or non-manual field")
        identifier, instance = manual, "study"
        path = workspace / "stage_a/manual" / (manual + ".txt")
        requires_reason = exclude
    if action == "reject" or requires_reason:
        if not reason.strip():
            raise ValueError("A rejection, exclusion, or non-found disposition requires --reason")
    reviewed_key = key(identifier, instance)
    decision = dict(action=action, field=reviewed_key, candidate_id=candidate_id, reviewer=reviewer,
                    reason=reason, at=now())
    if action == "accept":
        problems = source_problems(state)
        if problems:
            raise ValueError("\n".join(problems))
        data = (text + "\n").encode("utf-8") if explicit_text else path.read_bytes()
        text = data.decode("utf-8").strip()
        if not text or re.search(r"\[\[.*?\]\]|\b(?:TODO|TBD)\b", text, re.I):
            raise ValueError("Fill the editable text file before accepting; placeholders are not accepted")
        include = not exclude and (not candidate or candidate["record"]["status"] != "not_applicable")
        state["reviewed"][reviewed_key] = dict(candidate_id=candidate_id, text=text, include=include,
                                                reviewer=reviewer, reason=reason, accepted_at=decision["at"],
                                                edit_path=str(path.relative_to(workspace)),
                                                edit_sha256=digest(data))
        decision["accepted_text"] = text
        decision["include"] = include
    # Rejecting a new proposal never removes an earlier accepted value.
    if candidate_id:
        state["decisions"][candidate_id] = decision
    state["history"].append(decision)
    return (path, data) if action == "accept" and explicit_text else None


def escape(text):
    # Imported/reviewed field strings are plain text. They cannot create headings,
    # images, tables, code blocks, raw TeX, or links in the generated report.
    text = " ".join(text.split())
    return re.sub(r"([\\`*_{}\[\]<>#!|$~.+\-=])", r"\\\1", text)


def readiness(workspace, state=None, check_summary=True, check_manual=True):
    state = state or load(workspace)
    problems = provenance_problems(workspace, state) + source_problems(state)
    entries = fields(workspace)
    registry = entity_registry(state)
    for identifier, field in entries.items():
        if field["mode"] == "group" or (field["mode"] == "manual" and not check_manual) or (identifier.startswith("EXECUTIVE.") and not check_summary):
            continue
        records = {k: v for k, v in state["reviewed"].items() if k.startswith(identifier + "/")}
        scope = field["scope"]
        expected = [e["id"] for e in registry.values() if e["kind"] == scope] if scope != "study" else ["study"]
        if expected:
            for instance in expected:
                if key(identifier, instance) not in records:
                    problems.append(f"Unverified: {identifier}/{instance}")
        elif not records:
            problems.append(f"Unverified: {identifier} (no accepted records/disposition)")
        for reviewed_key, reviewed in records.items():
            for issue in stale_reasons(workspace, state, reviewed):
                problems.append(f"{reviewed_key}: {issue}")
    for candidate in state["candidates"].values():
        if not check_summary and candidate["field_id"].startswith("EXECUTIVE."):
            continue
        reviewed_key = key(candidate["field_id"], candidate["record"]["instance_id"])
        if reviewed_key not in state["reviewed"]:
            problems.append(f"Unverified imported item: {reviewed_key}")
    for reviewed_key, draft in state.get("ui_drafts", {}).items():
        if not check_summary and reviewed_key.startswith("EXECUTIVE."):
            continue
        if not check_manual and draft.get("manual"):
            continue
        accepted = state["reviewed"].get(reviewed_key)
        if not accepted or any(draft[k] != accepted[k] for k in ("candidate_id", "text", "include", "reason")):
            problems.append(f"Unapproved saved draft: {reviewed_key}")
    return list(dict.fromkeys(problems))


def verification_report(workspace):
    state = load(workspace)
    lines = ["# Stage A verification report", "", "Candidates are not approved facts. Edit the linked text file, then explicitly accept or reject its candidate ID.", "",
             "## Readiness", ""]
    blockers = readiness(workspace, state)
    lines.extend(["- " + escape(p) for p in blockers] or ["All fields have reviewed dispositions. Scientific/source and Word page checks remain manual."])
    for candidate_id, candidate in state["candidates"].items():
        record = candidate["record"]
        path = ensure_edit_file(workspace, candidate)
        reviewed_key = key(candidate["field_id"], record["instance_id"])
        accepted = state["reviewed"].get(reviewed_key)
        decision = state["decisions"].get(candidate_id, {}).get("action", "pending")
        lines.extend(["", f"## {candidate_id} — {escape(reviewed_key)}", "",
                      f"- Extraction status: {record['status']}; candidate decision: {decision}",
                      f"- Editable text: [open]({path.resolve().as_uri()})",
                      f"- Search scope: {escape(candidate['search_scope'])}",
                      f"- Explanation: {escape(record['explanation'])}", "",
                      "### Elsa original proposed text", "", escape(record["value"] or DISPOSITIONS[record["status"]]), "",
                      "### Current accepted text", "", escape(accepted["text"]) if accepted else "No accepted text."])
        if accepted:
            lines.extend(["", f"Included in report: {accepted['include']}; accepted candidate: {accepted['candidate_id'] or 'manual'}"])
        for source in record["sources"]:
            meta = state["requests"][candidate["request_id"]]["sources"][source["document_id"]]
            lines.extend(["", "### Source", "",
                          f"{escape(source['document_id'])} — {escape(meta['filename'])}; version {escape(meta['version'])}, {escape(meta['date'])}", "",
                          f"PDF position: {source['pdf_page'] or 'unavailable'}; printed label: {escape(source['printed_page'] or 'unavailable')}; section: {escape(source['section'] or 'unavailable')}", "",
                          "> " + escape(source["exact_excerpt"])])
    lines.extend(["", "## Manual fields", ""])
    for identifier, field in fields(workspace).items():
        if field["mode"] == "manual":
            path = workspace / "stage_a/manual" / (identifier + ".txt")
            lines.append(f"- {identifier}: [edit]({path.resolve().as_uri()})")
    path = workspace / "stage_a/verification.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Verification report: {path}")
    return path


def assemble(workspace):
    state = load(workspace)
    config = read_json(workspace / "review.json")
    registry = entity_registry(state)
    sections = []
    issues = readiness(workspace, state)

    def render_field(field, instance=None):
        identifier = field["id"]
        values = [(k, v) for k, v in state["reviewed"].items() if k.startswith(identifier + "/")]
        if instance is not None:
            values = [(k, v) for k, v in values if k == key(identifier, instance)]
        if not values:
            return [(None, "[[" + identifier + ("/" + instance if instance else "") + "]]" )]
        result = []
        for reviewed_key, reviewed in values:
            if not reviewed["include"]:
                continue
            label = registry.get(reviewed_key.split("/", 1)[1], {}).get("label")
            result.append((label, escape(reviewed["text"])))
        return result

    for section in catalog(workspace)["sections"]:
        lines = ["# " + section["title"], ""]
        if section["number"] in {7, 8}:
            scope = "primary_endpoint" if section["number"] == 7 else "secondary_endpoint"
            instances = [e for e in registry.values() if e["kind"] == scope]
            blocks = instances or [dict(id="none", label="Endpoint inventory/disposition")]
        else:
            blocks = [None]
        for entity in blocks:
            block_start = len(lines)
            if entity:
                lines.extend(["## " + escape(entity["label"]), ""])
            rendered = []
            for field in section["fields"]:
                if field["mode"] == "group":
                    rendered.append((field, None))
                    continue
                values = render_field(field, entity["id"] if entity else None)
                rendered.append((field, values))
            for index, (field, values) in enumerate(rendered):
                if values is None:
                    descendants = []
                    for child, child_values in rendered[index + 1:]:
                        if child["depth"] <= field["depth"]:
                            break
                        descendants.extend(child_values or [])
                    if descendants:
                        lines.extend(["    " * field["depth"] + "- **" + field["label"] + ":**", ""])
                    continue
                for label, text in values:
                    suffix = (" — " + escape(label)) if label and not entity else ""
                    title = field["label"] + suffix
                    if section["prose"]:
                        lines.extend(["**" + title + ":** " + text, ""])
                    else:
                        lines.extend(["    " * field["depth"] + "- **" + title + ":** " + text, ""])
            if len(lines) == block_start + (2 if entity else 0):
                lines.extend(["Omitted by reviewer-approved disposition.", ""])
        sections.append("\n".join(lines).strip())
    return config, "\n\n".join(sections) + "\n", issues


def accepted_uncertainties(workspace):
    """Informational accepted limits, separate from unresolved verification blockers."""
    state = load(workspace)
    notes = []
    for reviewed_key, reviewed in state["reviewed"].items():
        if reviewed["candidate_id"]:
            status = state["candidates"][reviewed["candidate_id"]]["record"]["status"]
            if status in {"not_found", "conflicting", "unreadable"}:
                notes.append(f"{reviewed_key}: reviewer accepted {status}; reason: {reviewed['reason']}")
        elif re.search(r"\bpending\b|not (?:independently )?(?:performed|verified)|not reproduced", reviewed["text"], re.I):
            notes.append(f"{reviewed_key}: accepted manual wording: {reviewed['text']}")
    return notes
