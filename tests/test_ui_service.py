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
        self.assertEqual(18, len(sa.load(self.workspace)["candidates"]))
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

    def test_remove_item_excludes_a_found_objective_but_keeps_it_visible(self):
        refs = {r["key"]: r for r in ui.objective_references(self.workspace)}
        primary = "OBJECTIVES.PRIMARY/O_SCORE"
        self.assertEqual("found", refs[primary]["status"])
        for key, ref in refs.items():
            ui.approve_item(self.workspace, key, ref["text"])
        with self.assertRaisesRegex(ValueError, "Explain why"):
            ui.remove_item(self.workspace, primary, "   ")
        with self.assertRaises(ValueError):
            ui.remove_item(self.workspace, "unknown/none", "duplicate")
        original_text = next(r for r in ui.objective_references(self.workspace) if r["key"] == primary)["text"]
        ui.remove_item(self.workspace, primary, "Duplicate of another stated objective")
        removed = next(r for r in ui.objective_references(self.workspace) if r["key"] == primary)
        self.assertTrue(removed["removed"])
        self.assertFalse(removed["included"])
        self.assertEqual("Duplicate of another stated objective", removed["reason"])
        self.assertEqual(original_text, removed["text"])  # wording preserved, just excluded
        self.assertNotIn(primary, [r["key"] for r in ui.memo_items(self.workspace)])
        ui.reset_item(self.workspace, primary)
        restored = next(r for r in ui.objective_references(self.workspace) if r["key"] == primary)
        self.assertFalse(restored["removed"])
        self.assertFalse(restored["approved"])

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

    def test_endpoints_item_approval_flag_and_section_lifecycle(self):
        refs = {r["key"]: r for r in ui.endpoint_references(self.workspace)}
        primary = "ENDPOINTS.PRIMARY/SCORE"
        with self.assertRaisesRegex(ValueError, "Enter the endpoint wording"):
            ui.approve_item(self.workspace, primary, "   ")
        with self.assertRaises(ValueError):
            ui.flag_item(self.workspace, primary, "premature")  # only approved wording can be flagged
        for key, ref in refs.items():
            ui.approve_item(self.workspace, key, ref["text"] + (" (edited)" if key == primary else ""))
        approved = {r["key"]: r for r in ui.endpoint_references(self.workspace)}
        self.assertTrue(all(r["approved"] for r in approved.values()))
        self.assertTrue(approved[primary]["text"].endswith("(edited)"))
        self.assertFalse(ui.section_done(self.workspace, ui.ENDPOINTS_SECTION))  # approving items does not finish the section
        ui.complete_section(self.workspace, ui.ENDPOINTS_SECTION)
        self.assertTrue(ui.section_done(self.workspace, ui.ENDPOINTS_SECTION))
        ui.flag_item(self.workspace, primary, "check the quote")
        self.assertFalse(ui.section_done(self.workspace, ui.ENDPOINTS_SECTION))  # a flag removes the section check
        ui.approve_item(self.workspace, primary, approved[primary]["text"])  # Looks good clears the flag
        self.assertTrue(ui.section_done(self.workspace, ui.ENDPOINTS_SECTION))

    def test_remove_endpoint_item_excludes_it_but_keeps_it_visible(self):
        refs = {r["key"]: r for r in ui.endpoint_references(self.workspace)}
        primary = "ENDPOINTS.PRIMARY/SCORE"
        self.assertEqual("found", refs[primary]["status"])
        for key, ref in refs.items():
            ui.approve_item(self.workspace, key, ref["text"])
        with self.assertRaisesRegex(ValueError, "Explain why"):
            ui.remove_item(self.workspace, primary, "   ")
        ui.remove_item(self.workspace, primary, "Duplicate of another stated endpoint")
        removed = next(r for r in ui.endpoint_references(self.workspace) if r["key"] == primary)
        self.assertTrue(removed["removed"])
        self.assertFalse(removed["included"])
        self.assertNotIn(primary, [r["key"] for r in ui.memo_items(self.workspace)])
        ui.reset_item(self.workspace, primary)
        restored = next(r for r in ui.endpoint_references(self.workspace) if r["key"] == primary)
        self.assertFalse(restored["removed"])
        self.assertFalse(restored["approved"])

    def test_endpoints_default_linked_to_their_reported_objective(self):
        choices = ui.objective_choices(self.workspace, "ENDPOINTS.PRIMARY")
        self.assertEqual([("O_SCORE", "Primary Objective 1"), ("O_RESPONSE", "Primary Objective 2")], choices)
        score = next(r for r in ui.endpoint_references(self.workspace) if r["key"] == "ENDPOINTS.PRIMARY/SCORE")
        self.assertEqual("O_SCORE", ui.endpoint_link(self.workspace, score))
        week24 = next(r for r in ui.endpoint_references(self.workspace) if r["key"] == "ENDPOINTS.SECONDARY/WEEK24")
        self.assertEqual("O_WEEK24", ui.endpoint_link(self.workspace, week24))
        groups = {name: [r["key"] for r in group] for _, name, group in ui.endpoint_subgroups(self.workspace, "ENDPOINTS.PRIMARY")}
        self.assertEqual(["ENDPOINTS.PRIMARY/SCORE"], groups["Primary Objective 1"])
        self.assertEqual(["ENDPOINTS.PRIMARY/RESPONSE"], groups["Primary Objective 2"])
        self.assertEqual([], groups["Not linked to a specific objective"])

    def test_reviewer_can_override_an_endpoint_link_and_fall_back_when_unresolved(self):
        ui.set_endpoint_link(self.workspace, "ENDPOINTS.PRIMARY/SCORE", ui.NOT_LINKED)
        moved = next(r for r in ui.endpoint_references(self.workspace) if r["key"] == "ENDPOINTS.PRIMARY/SCORE")
        self.assertEqual(ui.NOT_LINKED, ui.endpoint_link(self.workspace, moved))
        groups = {name: [r["key"] for r in group] for _, name, group in ui.endpoint_subgroups(self.workspace, "ENDPOINTS.PRIMARY")}
        self.assertEqual([], groups["Primary Objective 1"])
        self.assertEqual(["ENDPOINTS.PRIMARY/SCORE"], groups["Not linked to a specific objective"])
        ui.set_endpoint_link(self.workspace, "ENDPOINTS.PRIMARY/SCORE", "nonexistent")
        stale = next(r for r in ui.endpoint_references(self.workspace) if r["key"] == "ENDPOINTS.PRIMARY/SCORE")
        self.assertEqual(ui.NOT_LINKED, ui.endpoint_link(self.workspace, stale))  # an unresolvable override still falls back

    def test_unit_ready_and_complete_unit_require_every_objective_and_endpoint_approved(self):
        self.assertFalse(ui.unit_ready(self.workspace))
        for ref in ui.objective_references(self.workspace):
            ui.approve_item(self.workspace, ref["key"], ref["text"])
        self.assertFalse(ui.unit_ready(self.workspace))  # endpoints still unapproved
        with self.assertRaises(ValueError):
            ui.complete_unit(self.workspace)
        self.assertFalse(ui.unit_done(self.workspace))
        for ref in ui.endpoint_references(self.workspace):
            ui.approve_item(self.workspace, ref["key"], ref["text"])
        self.assertTrue(ui.unit_ready(self.workspace))
        ui.complete_unit(self.workspace)
        self.assertTrue(ui.unit_done(self.workspace))
        self.assertTrue(ui.all_sections_done(self.workspace))

    def test_memo_sections_interleaves_objectives_with_their_endpoints_and_locks_until_checked(self):
        for ref in ui.unit_items(self.workspace):
            ui.approve_item(self.workspace, ref["key"], ref["text"])
        ui.complete_unit(self.workspace)
        entries = ui.memo_sections(self.workspace)
        self.assertEqual({r["key"] for r in ui.memo_items(self.workspace)}, {ref["key"] for _, ref, _ in entries})
        self.assertEqual(len(ui.memo_items(self.workspace)), len(entries))  # no item appears twice
        keys = [ref["key"] for _, ref, _ in entries]
        score = keys.index("OBJECTIVES.PRIMARY/O_SCORE")
        score_endpoint = keys.index("ENDPOINTS.PRIMARY/SCORE")
        response = keys.index("OBJECTIVES.PRIMARY/O_RESPONSE")
        week24 = keys.index("OBJECTIVES.OTHER/O_WEEK24")
        week24_endpoint = keys.index("ENDPOINTS.SECONDARY/WEEK24")
        self.assertLess(score, score_endpoint)
        self.assertLess(score_endpoint, response)  # each objective's endpoint(s) come right after it
        self.assertLess(response, week24)  # primary objectives before secondary
        self.assertLess(week24, week24_endpoint)
        locked = {ref["key"]: locked for _, ref, locked in entries}
        self.assertTrue(locked["ENDPOINTS.PRIMARY/SCORE"])  # its objective isn't checked yet
        self.assertFalse(locked["OBJECTIVES.PRIMARY/O_SCORE"])
        ui.mark_checked(self.workspace, "OBJECTIVES.PRIMARY/O_SCORE")
        locked = {ref["key"]: locked for _, ref, locked in ui.memo_sections(self.workspace)}
        self.assertFalse(locked["ENDPOINTS.PRIMARY/SCORE"])  # unlocked once its objective is checked
        self.assertTrue(locked["ENDPOINTS.PRIMARY/RESPONSE"])  # a different objective's endpoint stays locked

    def test_other_endpoint_links_only_to_other_objectives(self):
        self.assertEqual({"O_WEEK4"}, {i for i, _ in ui.objective_choices(self.workspace, "ENDPOINTS.OTHER")})
        self.assertEqual({"O_WEEK24"}, {i for i, _ in ui.objective_choices(self.workspace, "ENDPOINTS.SECONDARY")})
        self.assertEqual({"O_SCORE", "O_RESPONSE"}, {i for i, _ in ui.objective_choices(self.workspace, "ENDPOINTS.PRIMARY")})
        other = [r for r in ui.endpoint_references(self.workspace) if r["group"] == "ENDPOINTS.OTHER"]
        self.assertEqual(["OTHER_LOOK"], [r["instance"] for r in other])
        self.assertEqual("O_WEEK4", ui.endpoint_link(self.workspace, other[0]))
        for ref in ui.unit_items(self.workspace):
            ui.approve_item(self.workspace, ref["key"], ref["text"])
        ui.complete_unit(self.workspace)
        keys = [ref["key"] for _, ref, _ in ui.memo_sections(self.workspace)]
        self.assertEqual(len(ui.memo_items(self.workspace)), len(keys))
        self.assertEqual(keys.index("OBJECTIVES.EXPLORATORY/O_WEEK4") + 1, keys.index("ENDPOINTS.OTHER/OTHER_LOOK"))
        groups = dict(sa.endpoint_objective_groups(sa.load(self.workspace)))
        self.assertEqual(1, len(groups["Other Objective 1"]))

    def test_memo_items_and_all_sections_done_span_every_list_section(self):
        self.assertFalse(ui.all_sections_done(self.workspace))
        for ref in ui.objective_references(self.workspace):
            ui.approve_item(self.workspace, ref["key"], ref["text"])
        ui.complete_section(self.workspace, ui.OBJECTIVES_SECTION)
        self.assertFalse(ui.all_sections_done(self.workspace))  # endpoints still open
        for ref in ui.endpoint_references(self.workspace):
            ui.approve_item(self.workspace, ref["key"], ref["text"])
        ui.complete_section(self.workspace, ui.ENDPOINTS_SECTION)
        self.assertTrue(ui.all_sections_done(self.workspace))
        keys = [r["key"] for r in ui.memo_items(self.workspace)]
        self.assertTrue(any(k.startswith("ENDPOINTS.") for k in keys))
        self.assertTrue(any(k.startswith("OBJECTIVES.") for k in keys))


if __name__ == "__main__":
    unittest.main()
