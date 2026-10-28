"""Stage A contract, provenance, reimport, verification and real build checks.

These tests exercise local behavior. They do not evaluate Elsa's extraction accuracy.
"""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import review
import stage_a as sa

PANDOC = os.environ.get("PANDOC") or shutil.which("pandoc")
ENTITIES = {
    "primary_objective": [dict(id="O1", kind="primary_objective", label="Primary objective")],
    "secondary_objective": [dict(id="O2", kind="secondary_objective", label="Secondary objective")],
    "primary_endpoint": [dict(id="SCORE", kind="primary_endpoint", label="SCORE"),
                         dict(id="RESPONSE", kind="primary_endpoint", label="RESPONSE")],
    "secondary_endpoint": [dict(id="WEEK24", kind="secondary_endpoint", label="Week 24 score")],
    "experimental_arm": [dict(id="LOW", kind="experimental_arm", label="Low dose"),
                         dict(id="HIGH", kind="experimental_arm", label="High dose")],
    "control_arm": [dict(id="PLACEBO", kind="control_arm", label="Placebo")],
    "interim_look": [],
}


def quiet(function, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return function(*args, **kwargs)


def sample_response(manifest):
    """Synthetic schema-compliant values; intentionally not an Elsa evaluation."""
    source_id = next(iter(manifest["sources"]))
    evidence = dict(document_id=source_id, pdf_page=None, printed_page=None, section="Synthetic test",
                    exact_excerpt="This is entirely fictional protocol text for a software test.")
    response = dict(schema_version=1, catalog_version=1, request_id=manifest["request_id"],
                    search_scope="Synthetic fixture; no PDF retrieval was performed.", entities=[], fields={})
    discovered = {}
    for spec in manifest["fields"].values():
        if spec["discovers_entities"]:
            for entity in ENTITIES[spec["scope"]]:
                discovered[entity["id"]] = entity
    response["entities"] = list(discovered.values())
    for identifier, spec in manifest["fields"].items():
        instances = spec["expected_instances"]
        if spec["scope"] != "study":
            if spec["discovers_entities"]:
                instances = [e["id"] for e in ENTITIES[spec["scope"]]] or ["none"]
            elif spec["scope"] == "interim_look" and not instances:
                instances = [e["id"] for e in ENTITIES["interim_look"]] or ["none"]
        response["fields"][identifier] = []
        for instance in instances:
            sources = [copy.deepcopy(evidence)]
            if manifest["summary_dependencies"]:
                sources = next(f["sources"] for f in manifest["accepted_facts"].values() if f["sources"])
            value = identifier + " for " + instance
            status = "found"
            explanation = ""
            if instance == "none":
                value, status, explanation = None, "not_applicable", "No interim looks are planned in this synthetic fixture."
            elif spec["mode"] == "verbatim":
                sources[0]["exact_excerpt"] = value
            response["fields"][identifier].append(dict(instance_id=instance, status=status, value=value,
                                                       sources=sources, explanation=explanation))
    return response


class StageATests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.workspace = self.directory / "workspace"
        quiet(review.initialize, self.workspace, "stage-a")
        self.source = self.directory / "protocol.txt"
        self.source.write_text("This is entirely fictional protocol text for a software test.\n")
        quiet(sa.register_source, self.workspace, self.source, "PROTOCOL", "protocol", "1.0", "2026-01-15", 20)

    def prepare(self, sections="3,4,5", fields=None):
        request_id = quiet(sa.prepare, self.workspace, sections, fields)
        return sa.load(self.workspace)["requests"][request_id]

    def import_payload(self, payload):
        path = self.directory / "elsa.json"
        path.write_text(json.dumps(payload, ensure_ascii=False))
        quiet(sa.import_response, self.workspace, path)
        return sa.load(self.workspace)

    def accept_candidates(self, state=None):
        state = state or sa.load(self.workspace)
        for candidate_id, candidate in state["candidates"].items():
            if candidate_id not in state["decisions"]:
                quiet(sa.review_item, self.workspace, candidate_id=candidate_id, action="accept",
                      reviewer="Fictional reviewer", reason="Synthetic test disposition")

    def complete_facts(self):
        for sections in ("3,4,5", "6,7,8", "2,9,10"):
            self.import_payload(sample_response(self.prepare(sections)))
            self.accept_candidates()

    def complete_review(self):
        self.complete_facts()
        self.import_payload(sample_response(self.prepare(fields="EXECUTIVE.FACTS")))
        self.accept_candidates()
        for identifier, field in sa.fields(self.workspace).items():
            if field["mode"] == "manual":
                path = self.workspace / "stage_a/manual" / (identifier + ".txt")
                path.write_text("Fictional reviewer supplied this manual disposition.\n")
                quiet(sa.review_item, self.workspace, manual=identifier, action="accept", reviewer="Fictional reviewer")
        config_path = self.workspace / "review.json"
        config = sa.read_json(config_path)
        config["submission"] = "SYNTHETIC SOFTWARE TEST"
        sa.write_json(config_path, config)

    def test_catalog_modes_and_stage_scope(self):
        fields = sa.fields(self.workspace)
        self.assertEqual("verbatim", fields["OBJECTIVES.PRIMARY"]["mode"])
        self.assertEqual("manual", fields["SAMPLE_SIZE.VERIFICATION"]["mode"])
        self.assertEqual("secondary_endpoint", fields["OTHER_ANALYSIS.SET"]["scope"])
        self.assertNotIn("EXECUTIVE.SUMMARY", fields)
        self.assertIn("EXECUTIVE.ASSESSMENT", fields)
        self.assertIn("every secondary", fields["OBJECTIVES.OTHER"]["instructions"])
        self.assertNotIn("flag a potential request", json.dumps(fields))

    def test_prepare_identity_schema_and_manual_exclusion(self):
        manifest = self.prepare()
        self.assertEqual(["study"], manifest["fields"]["DESIGN.POPULATION"]["expected_instances"])
        self.assertNotIn("SAMPLE_SIZE.VERIFICATION", manifest["fields"])
        self.assertNotIn("path", manifest["sources"]["PROTOCOL"])
        path = self.workspace / "stage_a/requests" / manifest["request_id"]
        self.assertTrue((path / "response.schema.json").exists())
        self.assertIn("Exclude all secondary", (path / "instructions.md").read_text())
        with self.assertRaisesRegex(ValueError, "manual"):
            self.prepare(fields="SPONSOR.COMMENTS")

    def test_strict_import_rejects_structure_and_domain_errors_atomically(self):
        manifest = self.prepare()
        good = sample_response(manifest)
        for mutate in (
            lambda p: p.update(extra=True),
            lambda p: p.update(schema_version=True),
            lambda p: p.update(catalog_version=99),
            lambda p: p["fields"].pop("OBJECTIVES.PRIMARY"),
            lambda p: p["fields"].update({"SPONSOR.COMMENTS": []}),
            lambda p: p["fields"]["DESIGN.POPULATION"][0].update(sources=[]),
            lambda p: p["fields"]["DESIGN.POPULATION"][0]["sources"][0].update(document_id="UNKNOWN"),
            lambda p: p["fields"]["DESIGN.POPULATION"][0]["sources"][0].update(pdf_page=True),
            lambda p: p["fields"]["DESIGN.POPULATION"][0]["sources"][0].update(pdf_page=21),
            lambda p: p["fields"]["OBJECTIVES.PRIMARY"][0].update(instance_id="O2"),
            lambda p: p["fields"]["OBJECTIVES.PRIMARY"][0].update(value="A paraphrase not present in the returned quotation."),
            lambda p: p["fields"]["OBJECTIVES.PRIMARY"].append(copy.deepcopy(p["fields"]["OBJECTIVES.PRIMARY"][0])),
        ):
            bad = copy.deepcopy(good)
            mutate(bad)
            before = (self.workspace / "stage_a/state.json").read_bytes()
            with self.assertRaises(ValueError):
                self.import_payload(bad)
            self.assertEqual(before, (self.workspace / "stage_a/state.json").read_bytes())
            self.assertFalse((self.workspace / "stage_a/imports").exists())

    def test_duplicate_keys_and_non_json_numbers_are_rejected(self):
        for text in ('{"request_id":"a","request_id":"b"}', '{"value":NaN}'):
            with self.assertRaises(ValueError):
                sa.strict_json(text)

    def test_original_bytes_preserved_and_pending_values_not_rendered(self):
        manifest = self.prepare()
        payload = sample_response(manifest)
        path = self.directory / "elsa.json"
        raw = json.dumps(payload, indent=3).encode()
        path.write_bytes(raw)
        run_id = quiet(sa.import_response, self.workspace, path)
        self.assertEqual(raw, (self.workspace / "stage_a/imports" / run_id / "original.json").read_bytes())
        _, body, blockers = sa.assemble(self.workspace)
        self.assertNotIn("DESIGN.POPULATION for study", body)
        self.assertIn("[[DESIGN.POPULATION]]", body)
        self.assertTrue(blockers)

    def test_edit_accept_and_reimport_preserve_original_and_reviewed_values(self):
        manifest = self.prepare(fields="DESIGN.POPULATION")
        self.import_payload(sample_response(manifest))
        state = sa.load(self.workspace)
        candidate_id = next(iter(state["candidates"]))
        quiet(sa.verification_report, self.workspace)
        edit_path = sa.candidate_path(self.workspace, candidate_id)
        edit_path.write_text("Reviewer revised the population wording.\n")
        quiet(sa.review_item, self.workspace, candidate_id=candidate_id, action="accept", reviewer="Reviewer A")
        original = sa.load(self.workspace)["candidates"][candidate_id]["record"]["value"]
        payload = sample_response(manifest)
        payload["fields"]["DESIGN.POPULATION"][0]["value"] = "New unreviewed proposal."
        self.import_payload(payload)
        state = sa.load(self.workspace)
        self.assertEqual("Reviewer revised the population wording.", state["reviewed"]["DESIGN.POPULATION/study"]["text"])
        self.assertEqual(original, state["candidates"][candidate_id]["record"]["value"])
        _, body, _ = sa.assemble(self.workspace)
        self.assertIn("Reviewer revised", body)
        self.assertNotIn("New unreviewed proposal", body)
        replacement_id = next(c for c in state["candidates"] if c != candidate_id)
        quiet(sa.review_item, self.workspace, candidate_id=replacement_id, action="reject", reviewer="Reviewer A", reason="Keep reviewed wording")
        self.assertEqual(candidate_id, sa.load(self.workspace)["reviewed"]["DESIGN.POPULATION/study"]["candidate_id"])
        edit_path.write_text("Unapproved change after acceptance.\n")
        self.assertTrue(any("unapproved changes" in p for p in sa.readiness(self.workspace)))

    def test_missing_dispositions_and_exclusion_are_explicit(self):
        manifest = self.prepare(fields="DESIGN.SITES")
        payload = sample_response(manifest)
        record = payload["fields"]["DESIGN.SITES"][0]
        record.update(status="not_found", value=None, sources=[], explanation="Searched design section only.")
        self.import_payload(payload)
        candidate_id = next(iter(sa.load(self.workspace)["candidates"]))
        with self.assertRaisesRegex(ValueError, "reason"):
            quiet(sa.review_item, self.workspace, candidate_id=candidate_id, action="accept", reviewer="R")
        quiet(sa.review_item, self.workspace, candidate_id=candidate_id, action="accept", reviewer="R", reason="Accept limited-search disposition", exclude=True)
        self.assertFalse(sa.load(self.workspace)["reviewed"]["DESIGN.SITES/study"]["include"])

    def test_secondary_scope_and_endpoint_associations(self):
        self.import_payload(sample_response(self.prepare()))
        self.accept_candidates()
        manifest = self.prepare("6,7,8")
        self.assertEqual(["SCORE", "RESPONSE"], manifest["fields"]["PRIMARY_ANALYSIS.METHOD"]["expected_instances"])
        self.assertEqual(["WEEK24"], manifest["fields"]["OTHER_ANALYSIS.METHOD"]["expected_instances"])
        payload = sample_response(manifest)
        payload["fields"]["PRIMARY_ANALYSIS.METHOD"][0]["instance_id"] = "WEEK24"
        with self.assertRaisesRegex(ValueError, "entity"):
            self.import_payload(payload)
        payload = sample_response(manifest)
        payload["fields"]["PRIMARY_ANALYSIS.METHOD"].pop()
        with self.assertRaisesRegex(ValueError, "missing requested instances"):
            self.import_payload(payload)

    def test_dependency_inventory_required_before_analysis(self):
        with self.assertRaisesRegex(ValueError, "definitions/inventory first"):
            self.prepare("7")

    def test_interim_discovery_covers_each_look_in_same_request(self):
        looks = [dict(id="LOOK1", kind="interim_look", label="First look"),
                 dict(id="LOOK2", kind="interim_look", label="Second look")]
        with patch.dict(ENTITIES, interim_look=looks):
            manifest = self.prepare("9")
            payload = sample_response(manifest)
            self.import_payload(payload)
            payload["fields"]["INTERIM.TIMING"].pop()
            with self.assertRaisesRegex(ValueError, "each discovered entity"):
                self.import_payload(payload)

    def test_conflict_and_inapplicability_require_evidence(self):
        manifest = self.prepare(fields="DESIGN.POPULATION")
        payload = sample_response(manifest)
        item = payload["fields"]["DESIGN.POPULATION"][0]
        item.update(status="not_applicable", value=None, explanation="Proposed disposition", sources=[])
        with self.assertRaisesRegex(ValueError, "inapplicability requires evidence"):
            self.import_payload(payload)
        item.update(status="conflicting", sources=[dict(document_id="PROTOCOL", pdf_page=1,
                    printed_page="1", section="1", exact_excerpt="First statement")])
        item["sources"].append(copy.deepcopy(item["sources"][0]))
        with self.assertRaisesRegex(ValueError, "competing source passages"):
            self.import_payload(payload)
        item["sources"][1]["exact_excerpt"] = "A conflicting second statement"
        self.import_payload(payload)

    def test_fictional_pilot_fixture_matches_sources_and_approves_nothing(self):
        import demo_stage_a
        destination = self.directory / "pilot"
        quiet(demo_stage_a.create, destination)
        state = sa.load(destination)
        self.assertEqual({}, state["reviewed"])
        self.assertEqual(16, len(state["candidates"]))
        text = " ".join((destination / "inputs/protocol.md").read_text().split())
        for candidate in state["candidates"].values():
            for source in candidate["record"]["sources"]:
                self.assertIn(" ".join(source["exact_excerpt"].split()), text)
        self.assertEqual({"O_WEEK24"}, {c["record"]["instance_id"] for c in state["candidates"].values() if c["field_id"] == "OBJECTIVES.OTHER"})

    def test_cli_defaults_to_stage_a_and_does_not_migrate_legacy(self):
        import subprocess
        target = self.directory / "cli-review"
        result = subprocess.run([sys.executable, str(ROOT / "scripts/review.py"), "init", str(target)], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(sa.active(target))
        legacy = self.directory / "legacy"
        quiet(review.initialize, legacy)
        self.assertFalse(sa.active(legacy))
        self.assertFalse((legacy / "stage_a").exists())

    def test_source_changes_and_provenance_tampering_detected(self):
        manifest = self.prepare(fields="DESIGN.POPULATION")
        self.import_payload(sample_response(manifest))
        self.accept_candidates()
        self.source.write_text("Changed source bytes.")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.prepare(fields="DESIGN.POPULATION")
        quiet(sa.register_source, self.workspace, self.source, "PROTOCOL", "protocol", "2.0", "2026-02-01")
        self.assertTrue(any("source version" in p for p in sa.readiness(self.workspace)))
        with self.assertRaisesRegex(ValueError, "registry changed"):
            self.import_payload(sample_response(manifest))
        run_id = next(iter(sa.load(self.workspace)["imports"]))
        (self.workspace / "stage_a/imports" / run_id / "original.json").write_text("{}")
        self.assertTrue(any("Provenance file" in p for p in sa.readiness(self.workspace)))

    def test_plain_text_cannot_inject_report_markdown(self):
        manifest = self.prepare(fields="DESIGN.POPULATION")
        payload = sample_response(manifest)
        payload["fields"]["DESIGN.POPULATION"][0]["value"] = '# Invented section\n![image](https://invalid.example/a) $x$ | table'
        self.import_payload(payload)
        self.accept_candidates()
        _, body, _ = sa.assemble(self.workspace)
        self.assertNotIn("\n# Invented", body)
        self.assertNotIn("![image]", body)
        self.assertIn("\\# Invented", body)

    def test_summary_follows_verified_facts_and_becomes_stale(self):
        with self.assertRaisesRegex(ValueError, "factual fields"):
            self.prepare(fields="EXECUTIVE.FACTS")
        self.complete_facts()
        manifest = self.prepare(fields="EXECUTIVE.FACTS")
        payload = sample_response(manifest)
        bad = copy.deepcopy(payload)
        bad["fields"]["EXECUTIVE.FACTS"][0]["sources"][0]["exact_excerpt"] = "A newly invented summary quotation"
        with self.assertRaisesRegex(ValueError, "accepted facts"):
            self.import_payload(bad)
        self.import_payload(payload)
        self.accept_candidates()
        state = sa.load(self.workspace)
        cid = state["reviewed"]["DESIGN.POPULATION/study"]["candidate_id"]
        sa.candidate_path(self.workspace, cid).write_text("Changed accepted population.\n")
        quiet(sa.review_item, self.workspace, candidate_id=cid, action="accept", reviewer="R")
        self.assertTrue(any("summary facts changed" in p for p in sa.readiness(self.workspace)))

    def test_final_verification_cannot_be_bypassed_by_global_flags(self):
        args = SimpleNamespace(workspace=self.workspace, output=self.directory / "final.md", final=True,
                               reviewer_approved=True, acknowledge_unresolved=True)
        with self.assertRaisesRegex(ValueError, "cannot bypass verification"):
            quiet(review.build, args)
        self.complete_review()
        self.assertEqual([], sa.readiness(self.workspace))
        quiet(review.build, args)
        self.assertNotIn("DRAFT", args.output.read_text())
        self.assertIn("Reviewer assessment", args.output.read_text())
        self.assertNotIn("exact_excerpt", args.output.read_text())

    @unittest.skipUnless(PANDOC, "Set PANDOC for the real Word conversion test")
    def test_stage_a_word_build_from_complete_review(self):
        self.complete_review()
        args = SimpleNamespace(workspace=self.workspace, output=self.directory / "memo.docx", final=True,
                               reviewer_approved=True, acknowledge_unresolved=False, pandoc=PANDOC, reference_doc=None)
        quiet(review.build, args)
        with ZipFile(args.output) as archive:
            document = archive.read("word/document.xml").decode()
            self.assertIn("SYNTHETIC SOFTWARE TEST", document)
            self.assertIn("SCORE", document)
            self.assertIn("RESPONSE", document)
            self.assertNotIn("exact_excerpt", document)


if __name__ == "__main__":
    unittest.main()
