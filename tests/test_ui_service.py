"""Local UI services: managed files, saved drafts, atomic approvals and retries."""
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import stage_a as sa
import ui_service as ui


class UIServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="xyz UI tests ")
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, XYZ_REVIEWS_DIR=str(Path(self.temp.name) / "Reviews with spaces"))
        self.env.start()
        self.addCleanup(self.env.stop)
        self.workspace = ui.create_review("Fictional review", "Reviewer", demo=True)

    def test_managed_sources_persist_versions_and_deduplicate(self):
        pdf = (ROOT / "tests/fixtures/sample.pdf").read_bytes()
        ui.store_source(self.workspace, "../protocol file.pdf", pdf, "protocol", "2", "unknown")
        state = sa.load(self.workspace)
        path = Path(state["sources"]["PROTOCOL"]["path"])
        self.assertTrue(path.is_relative_to(self.workspace))
        self.assertEqual("protocol file.pdf", path.name)
        self.assertEqual(pdf, path.read_bytes())
        old_version = sa.public_source(state["sources"]["PROTOCOL"])
        request_id = ui.create_request(self.workspace, 0)
        self.assertTrue(request_id)
        ui.store_source(self.workspace, "protocol file.pdf", pdf + b"\n% new version", "protocol", "3", "unknown")
        versions = ui.source_versions(self.workspace)
        self.assertFalse(versions[sa.object_hash(old_version)]["current"])
        self.assertEqual(pdf, Path(versions[sa.object_hash(old_version)]["path"]).read_bytes())
        first = ui.store_source(self.workspace, "background.pdf", pdf, "background")
        second = ui.store_source(self.workspace, "background.pdf", pdf, "background")
        self.assertEqual(first, second)
        with self.assertRaisesRegex(ValueError, "PDF"):
            ui.store_source(self.workspace, "bad.pdf", b"not a pdf", "protocol")

    def test_request_and_import_clicks_are_idempotent(self):
        first = ui.create_request(self.workspace, 0)
        second = ui.create_request(self.workspace, 0)
        self.assertEqual(first, second)
        raw = (self.workspace / "simulated_elsa_response.json").read_bytes()
        run, created = ui.import_bytes(self.workspace, raw)
        self.assertFalse(created)
        self.assertIn(run, sa.load(self.workspace)["imports"])
        self.assertEqual(17, len(sa.load(self.workspace)["candidates"]))
        before = (self.workspace / "stage_a/state.json").read_bytes()
        with self.assertRaises(ValueError):
            ui.import_bytes(self.workspace, b'{"request_id": "unknown"}')
        self.assertEqual(before, (self.workspace / "stage_a/state.json").read_bytes())

    def test_section_approval_validates_all_before_any_commit(self):
        items = ui.section_items(self.workspace, 3)
        first, last = items[0], items[-1]
        ui.save_draft(self.workspace, first["key"], "Edited first objective", True, "", first["candidate_id"])
        ui.save_draft(self.workspace, last["key"], "", True, "", last["candidate_id"])
        before = (self.workspace / "stage_a/state.json").read_bytes()
        originals = {p: p.read_bytes() for p in (self.workspace / "stage_a/edits").glob("*.txt")}
        with self.assertRaisesRegex(ValueError, "Fill the editable"):
            ui.approve_section(self.workspace, 3, "Reviewer")
        self.assertEqual(before, (self.workspace / "stage_a/state.json").read_bytes())
        self.assertEqual({}, sa.load(self.workspace)["reviewed"])
        self.assertTrue(all(p.read_bytes() == data for p, data in originals.items()))
        ui.save_draft(self.workspace, last["key"], "Secondary objective verified", True, "", last["candidate_id"])
        ui.approve_section(self.workspace, 3, "Reviewer")
        self.assertEqual(4, len(sa.load(self.workspace)["reviewed"]))
        self.assertEqual("Approved", ui.section_statuses(self.workspace)[3])
        self.assertEqual(("Review sections", 4, 0), ui.next_step(self.workspace))

    def test_section_approval_rolls_back_files_on_failed_state_save(self):
        item = ui.section_items(self.workspace, 3)[0]
        ui.save_draft(self.workspace, item["key"], "New draft", True, "", item["candidate_id"])
        originals = {p: p.read_bytes() for p in (self.workspace / "stage_a/edits").glob("*.txt")}
        with patch.object(sa, "save", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                ui.approve_section(self.workspace, 3, "Reviewer")
        self.assertEqual({}, sa.load(self.workspace)["reviewed"])
        self.assertTrue(all(p.read_bytes() == data for p, data in originals.items()))

    def test_new_proposal_keeps_accepted_wording_until_chosen(self):
        ui.approve_section(self.workspace, 3, "Reviewer")
        item = ui.section_items(self.workspace, 3)[0]
        payload = sa.read_json(self.workspace / "simulated_elsa_response.json")
        value = payload["fields"][item["field"]["id"]][0]
        value["value"] = "A new quoted objective"
        value["sources"][0]["exact_excerpt"] = value["value"]
        ui.import_bytes(self.workspace, json.dumps(payload).encode())
        current = ui.section_items(self.workspace, 3)[0]
        self.assertEqual(item["candidate_id"], current["candidate_id"])
        self.assertEqual(item["text"], current["text"])
        new_id = current["proposals"][-1]["id"]
        ui.choose_candidate(self.workspace, current["key"], new_id)
        self.assertTrue(any("Unapproved saved draft" in issue for issue in sa.readiness(self.workspace)))
        self.assertEqual("Needs review", ui.section_statuses(self.workspace)[3])
        _, body, _ = sa.assemble(self.workspace)
        self.assertNotIn("A new quoted objective", body)
        ui.approve_section(self.workspace, 3, "Reviewer")
        self.assertEqual(new_id, sa.load(self.workspace)["reviewed"][item["key"]]["candidate_id"])

    def test_drafts_persist_and_do_not_change_accepted_snapshot(self):
        ui.approve_section(self.workspace, 3, "Reviewer")
        item = ui.section_items(self.workspace, 3)[0]
        ui.save_draft(self.workspace, item["key"], "My unapproved edit", True, "", item["candidate_id"])
        self.assertEqual("My unapproved edit", ui.section_items(self.workspace, 3)[0]["text"])
        self.assertNotEqual("My unapproved edit", sa.load(self.workspace)["reviewed"][item["key"]]["text"])
        self.assertTrue(any("Unapproved saved draft" in issue for issue in sa.readiness(self.workspace)))
        self.assertTrue(any(r["path"] == self.workspace for r in ui.list_reviews()))

    def test_manual_field_section_and_draft_markdown(self):
        item = ui.section_items(self.workspace, 12)[0]
        ui.save_draft(self.workspace, item["key"], "None", True, "", None, manual=True)
        ui.approve_section(self.workspace, 12, "Reviewer")
        path = ui.build_report(self.workspace, word=False)
        self.assertIn("Review-team comments", path.read_text())
        self.assertIn("None", path.read_text())
        with self.assertRaisesRegex(ValueError, "cannot bypass"):
            ui.build_report(self.workspace, final=True, word=False)

    def test_older_review_gains_other_objectives_field_when_nothing_is_approved(self):
        workspace = ui.create_review("Older review", "Reviewer")
        ui.store_source(workspace, "protocol.pdf", (ROOT / "tests/fixtures/sample.pdf").read_bytes(), "protocol")
        catalog = sa.read_json(workspace / "stage_a/catalog.json")
        for section in catalog["sections"]:
            section["fields"] = [f for f in section["fields"] if f["id"] != "OBJECTIVES.EXPLORATORY"]
        sa.write_json(workspace / "stage_a/catalog.json", catalog)
        request_id = ui.prepare_objectives(workspace)
        self.assertIn("OBJECTIVES.EXPLORATORY", sa.load(workspace)["requests"][request_id]["fields"])

    def test_item_approval_flag_and_section_lifecycle(self):
        refs = {r["key"]: r for r in ui.objective_references(self.workspace)}
        primary = "OBJECTIVES.PRIMARY/O_SCORE"
        with self.assertRaisesRegex(ValueError, "Enter the objective wording"):
            ui.approve_item(self.workspace, primary, "   ")
        with self.assertRaises(ValueError):
            ui.flag_item(self.workspace, primary, "premature")  # only approved wording can be flagged
        for key, ref in refs.items():
            ui.approve_item(self.workspace, key, ref["text"] + (" (edited)" if key == primary else ""))
        approved = {r["key"]: r for r in ui.objective_references(self.workspace)}
        self.assertTrue(all(r["approved"] for r in approved.values()))
        self.assertTrue(approved[primary]["text"].endswith("(edited)"))
        self.assertNotEqual(approved[primary]["original"], approved[primary]["text"])  # Elsa's text kept
        self.assertFalse(ui.section_done(self.workspace, 3))  # approving items does not finish the section
        ui.complete_section(self.workspace, 3)
        self.assertTrue(ui.section_done(self.workspace, 3))
        ui.flag_item(self.workspace, primary, "check the quote")
        self.assertFalse(ui.section_done(self.workspace, 3))  # a flag removes the section check
        ui.approve_item(self.workspace, primary, approved[primary]["text"])  # Looks good clears the flag
        self.assertTrue(ui.section_done(self.workspace, 3))
        ui.reset_item(self.workspace, primary)
        self.assertFalse(ui.section_done(self.workspace, 3))
        self.assertEqual(refs[primary]["original"], next(r for r in ui.objective_references(self.workspace) if r["key"] == primary)["text"])

    def test_memo_check_and_export_ready_follow_the_memo_content(self):
        for ref in ui.objective_references(self.workspace):
            ui.approve_item(self.workspace, ref["key"], ref["text"])
        keys = [r["key"] for r in ui.memo_items(self.workspace)]
        self.assertTrue(keys and all(not r["checked"] for r in ui.memo_items(self.workspace)))
        for key in keys:
            ui.mark_checked(self.workspace, key)
        self.assertTrue(all(r["checked"] for r in ui.memo_items(self.workspace)))
        ui.mark_export_ready(self.workspace)
        self.assertTrue(ui.export_ready(self.workspace))
        ui.approve_item(self.workspace, keys[0], "Different wording")
        self.assertFalse(ui.export_ready(self.workspace))  # changed content must be re-checked
        self.assertFalse(next(r for r in ui.memo_items(self.workspace) if r["key"] == keys[0])["checked"])


if __name__ == "__main__":
    unittest.main()
