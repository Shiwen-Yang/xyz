"""Screen interaction tests; optional when requirements-ui.txt is not installed."""
import importlib.util
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

HAS_UI = importlib.util.find_spec("streamlit") is not None and importlib.util.find_spec("streamlit_pdf_viewer") is not None
if HAS_UI:
    from streamlit.testing.v1 import AppTest


def svc_request(workspace):
    return ui.objectives_request(workspace)


@unittest.skipUnless(HAS_UI, "Install requirements-ui.txt to run Streamlit interaction tests")
class StreamlitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="xyz streamlit ")
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, XYZ_REVIEWS_DIR=self.temp.name)
        self.env.start()
        self.addCleanup(self.env.stop)

    def start(self):
        # Importing the PDF viewer's local rendering stack can take more than
        # 20 seconds on a cold Windows or CI process.  This remains an in-process
        # test; the application itself does not wait on a network service.
        return AppTest.from_file(str(ROOT / "app.py"), default_timeout=45).run()

    def button(self, app, label):
        return next(button for button in app.button if button.label == label)

    def assert_clean(self, app):
        self.assertEqual([], [exception.message for exception in app.exception])

    def demo(self):
        app = self.start()
        self.button(app, "Try fictional example").click().run()
        self.assert_clean(app)
        return app, Path(app.session_state["workspace"])

    def objectives_payload(self, request_id, page=1, excerpt="Primary Objective(s):"):
        def record(instance, value):
            return dict(instance_id=instance, status="found", value=value, explanation="", sources=[dict(
                document_id="PROTOCOL", pdf_page=page, printed_page=None, section="Objectives", exact_excerpt=excerpt)])
        return dict(schema_version=1, catalog_version=1, request_id=request_id, search_scope="Test PDF only.",
                    entities=[dict(id="P1", kind="primary_objective", label="Primary objective 1"),
                              dict(id="S1", kind="secondary_objective", label="Secondary objective 1")],
                    fields={"OBJECTIVES.PRIMARY": [record("P1", excerpt)], "OBJECTIVES.OTHER": [record("S1", excerpt)],
                            "OBJECTIVES.EXPLORATORY": [dict(instance_id="none", status="not_found", value=None, sources=[],
                                                            explanation="No exploratory objectives in the test PDF.")]})

    def workspace_with_pdf(self):
        app = self.start()
        app.text_input[0].input("Study review")
        app.text_input[1].input("Reviewer")
        self.button(app, "Create review").click().run()
        pdf = (ROOT / "tests/fixtures/sample.pdf").read_bytes()
        app.file_uploader[0].set_value(("protocol.pdf", pdf, "application/pdf"))
        self.button(app, "Save documents").click().run()
        self.assert_clean(app)
        self.button(app, "Next: review workspace →").click().run()
        self.assert_clean(app)
        return app, Path(app.session_state["workspace"])

    def test_prepare_prompt_then_reject_bad_response(self):
        app, workspace = self.workspace_with_pdf()
        self.button(app, "Prepare prompt").click().run()
        self.assert_clean(app)
        request_id = svc_request(workspace)
        self.assertTrue(any(request_id in code.value for code in app.code))
        self.assertTrue(self.button(app, "← Back").disabled)
        self.button(app, "Next →").click().run()
        self.assertFalse(app.code)  # the prompt step is hidden after moving on
        self.assertTrue(self.button(app, "Next →").disabled)  # nothing loaded yet
        app.text_area(key=f"paste:{workspace.name}").input("{}").run()
        self.button(app, "Load pasted JSON").click().run()
        self.assertTrue(app.error)
        self.assertEqual({}, sa.load(workspace)["imports"])

    def load_objectives(self, app, workspace, payload=None):
        self.button(app, "Prepare prompt").click().run()
        request_id = svc_request(workspace)
        ui.import_bytes(workspace, json.dumps(payload or self.objectives_payload(request_id)).encode())
        self.button(app, "Next →").click().run()
        self.button(app, "Next →").click().run()
        self.assert_clean(app)

    def approve_all(self, app, count=3):
        for index in range(count):
            [b for b in app.button if b.label == "Looks good"][index].click().run()

    def box(self, app, workspace, key):
        return next(w for w in app.text_area if w.key.startswith(f"objtext:{workspace.name}:{key}:"))

    def test_load_from_downloads_folder_lists_references_and_highlights(self):
        app, workspace = self.workspace_with_pdf()
        self.button(app, "Prepare prompt").click().run()
        request_id = svc_request(workspace)
        downloads = Path(self.temp.name) / "downloads"
        downloads.mkdir()
        (downloads / ui.elsa_filename(request_id)).write_text(json.dumps(self.objectives_payload(request_id)))
        self.button(app, "Next →").click().run()
        app.text_input(key=f"folder:{workspace.name}").input(str(downloads)).run()
        self.button(app, "Load response from this folder").click().run()
        self.assert_clean(app)
        self.assertEqual(3, len(sa.load(workspace)["candidates"]))
        self.assertEqual(str(downloads), sa.read_json(workspace / "review.json")["ui_download_dir"])
        self.assertFalse([b for b in app.button if b.label == "Locate reference"])  # still on step 2
        self.button(app, "Next →").click().run()
        headings = [m.value for m in app.markdown if m.value.startswith("#### ")]
        self.assertEqual(["#### Primary objectives", "#### Secondary objectives", "#### Other objectives (exploratory, etc.)"], headings)
        names = [e.label for e in app.expander if "Objective" in e.label and not e.label[0].isdigit()]
        self.assertEqual(["Primary Objective 1", "Secondary Objective 1", "Other Objectives (none found by Elsa)"], names)
        locate = [b for b in app.button if b.label == "Locate reference"]
        self.assertEqual(3, len(locate))
        self.assertTrue(locate[2].disabled)  # the "not found" item cites nothing
        locate[0].click().run()
        self.assert_clean(app)
        args = json.loads(app.get("component_instance")[-1].proto.json_args)
        self.assertEqual([1], args["pages_to_render"])
        self.assertTrue(args["annotations"])
        self.assertEqual(1, args["annotations"][0]["page"])

    def test_locate_reference_cycles_through_several_passages(self):
        app, workspace = self.workspace_with_pdf()
        self.button(app, "Prepare prompt").click().run()
        payload = self.objectives_payload(svc_request(workspace))
        record = payload["fields"]["OBJECTIVES.PRIMARY"][0]
        record["value"] = "Executive Summary:"
        record["sources"] = [dict(record["sources"][0], pdf_page=1, exact_excerpt="Executive Summary:"),
                             dict(record["sources"][0], pdf_page=2, exact_excerpt="Analyses for Other Important Endpoint(s):")]
        ui.import_bytes(workspace, json.dumps(payload).encode())
        self.button(app, "Next →").click().run()
        self.button(app, "Next →").click().run()
        pages = []
        for _ in range(3):
            next(b for b in app.button if b.label == "Locate reference").click().run()
            self.assert_clean(app)
            pages.append(json.loads(app.get("component_instance")[-1].proto.json_args)["pages_to_render"][0])
        self.assertEqual([1, 2, 1], pages)

    def test_looks_good_approves_collapses_and_reset_undoes_it(self):
        app, workspace = self.workspace_with_pdf()
        self.load_objectives(app, workspace)
        self.box(app, workspace, "OBJECTIVES.PRIMARY/P1").input("Edited primary objective").run()
        self.assertTrue(any("not confirmed" in c.value for c in app.caption))
        next(b for b in app.button if b.label == "Looks good").click().run()
        self.assert_clean(app)
        reviewed = sa.load(workspace)["reviewed"]["OBJECTIVES.PRIMARY/P1"]
        self.assertEqual("Edited primary objective", reviewed["text"])
        first = next(e for e in app.expander if e.label.endswith("Primary Objective 1"))
        self.assertEqual("✅ Primary Objective 1", first.label)
        self.assertFalse(first.proto.expanded)  # a finished bulletin collapses
        candidate = sa.load(workspace)["candidates"][reviewed["candidate_id"]]
        self.assertEqual("Primary Objective(s):", candidate["record"]["value"])  # Elsa's original untouched
        next(b for b in app.button if b.label == "↻").click().run()
        self.assert_clean(app)
        self.assertNotIn("OBJECTIVES.PRIMARY/P1", sa.load(workspace)["reviewed"])
        self.assertEqual("Primary Objective(s):", self.box(app, workspace, "OBJECTIVES.PRIMARY/P1").value)

    def test_finish_section_marks_header_and_unlocks_export(self):
        app, workspace = self.workspace_with_pdf()
        self.load_objectives(app, workspace)
        finish = self.button(app, "Finish this section ✓")
        self.assertTrue(finish.disabled)
        self.assertTrue(self.button(app, "Continue to Export →").disabled)
        self.approve_all(app)
        self.assert_clean(app)
        self.assertIn("OBJECTIVES.EXPLORATORY/none", sa.load(workspace)["reviewed"])  # confirmed "none stated"
        self.assertFalse(sa.load(workspace)["reviewed"]["OBJECTIVES.EXPLORATORY/none"]["include"])
        self.button(app, "Finish this section ✓").click().run()
        self.assert_clean(app)
        header = next(e for e in app.expander if e.label.endswith("3. Primary Objective(s)"))
        self.assertEqual("✅ 3. Primary Objective(s)", header.label)
        self.assertFalse(header.proto.expanded)
        self.button(app, "Continue to Export →").click().run()
        self.assertEqual("Export", app.session_state["screen"])

    def finish_objectives(self, app, workspace):
        self.load_objectives(app, workspace)
        self.approve_all(app)
        self.button(app, "Finish this section ✓").click().run()
        self.button(app, "Continue to Export →").click().run()
        self.assert_clean(app)

    def test_export_check_flag_reopens_bulletin_and_all_set_requires_every_check(self):
        app, workspace = self.workspace_with_pdf()
        self.finish_objectives(app, workspace)
        self.assertTrue(self.button(app, "All Set ✓").disabled)
        app.text_input(key="flagnote:OBJECTIVES.PRIMARY/P1").input("Wrong page").run()
        next(b for b in app.button if b.key == "mflag:OBJECTIVES.PRIMARY/P1").click().run()
        self.assert_clean(app)
        self.assertEqual("Wrong page", sa.load(workspace)["ui_flags"]["OBJECTIVES.PRIMARY/P1"]["note"])
        next(b for b in app.button if b.key == "mgood:OBJECTIVES.OTHER/S1").click().run()
        self.assertTrue(self.button(app, "All Set ✓").disabled)  # a flag blocks it
        self.assertTrue(any("flagged" in w.value.lower() for w in app.warning))
        self.button(app, "← Back to Review workspace to edit").click().run()
        self.assertEqual("Review workspace", app.session_state["screen"])
        reopened = next(e for e in app.expander if e.label.endswith("Primary Objective 1"))
        self.assertTrue(reopened.label.startswith("🚩"))
        self.assertTrue(reopened.proto.expanded)
        self.assertTrue(any("Wrong page" in e.value for e in app.error))
        self.assertTrue(self.button(app, "Continue to Export →").disabled)  # section lost its check
        next(b for b in app.button if b.label == "Looks good" and b.key.endswith("OBJECTIVES.PRIMARY/P1:" + sa.load(workspace)["reviewed"]["OBJECTIVES.PRIMARY/P1"]["candidate_id"])).click().run()
        self.assertNotIn("OBJECTIVES.PRIMARY/P1", sa.load(workspace).get("ui_flags", {}))
        self.assertFalse(self.button(app, "Continue to Export →").disabled)
        self.button(app, "Continue to Export →").click().run()
        next(b for b in app.button if b.key == "mgood:OBJECTIVES.PRIMARY/P1").click().run()
        self.button(app, "All Set ✓").click().run()
        self.assert_clean(app)
        self.assertTrue(ui.export_ready(workspace))
        self.assertTrue(any(w.label == "Download draft Markdown" for w in app.get("download_button")))

    def test_progress_indicator_replaces_sidebar_navigation(self):
        app = self.start()
        self.assertEqual(0, len(app.sidebar.radio))
        self.assertTrue(any(m.value.startswith("**● 1. Set up**") for m in app.markdown))
        app, workspace = self.workspace_with_pdf()
        self.assertTrue(any(m.value.startswith(":green[✓ 1. Set up]") for m in app.markdown))
        self.assertTrue(any(m.value.startswith("**● 2. Review workspace**") for m in app.markdown))

    def test_saved_review_can_be_reopened_from_set_up(self):
        workspace = ui.create_review("Saved one", "Reviewer")
        app = self.start()
        app.selectbox(key="saved_review").set_value(str(workspace)).run()
        self.button(app, "Open review").click().run()
        self.assert_clean(app)
        self.assertEqual(str(workspace), app.session_state["workspace"])

    def test_other_sections_are_listed_but_not_yet_available(self):
        app, workspace = self.demo()
        self.assertEqual("Review workspace", app.session_state["screen"])
        labels = [e.label for e in app.expander if e.label[0].isdigit()]
        self.assertEqual(13, len(labels))
        self.assertIn("3. Primary Objective(s)", labels)

    @unittest.skipUnless(os.environ.get("PANDOC") or shutil.which("pandoc"), "Set PANDOC for Word download control test")
    def test_word_generation_exposes_download_control(self):
        app, workspace = self.demo()
        for item in ui.objective_references(workspace):
            ui.approve_item(workspace, item["key"], item["text"])
            ui.mark_checked(workspace, item["key"])
        ui.mark_export_ready(workspace)
        app.session_state["screen"] = "Export"
        app.run()
        pandoc = os.environ.get("PANDOC") or shutil.which("pandoc")
        next(w for w in app.text_input if w.label == "Pandoc executable (if not on PATH)").input(pandoc)
        self.button(app, "Remember Word setting").click().run()
        self.button(app, "Create draft Word").click().run()
        self.assert_clean(app)
        self.assertTrue((workspace / "exports/review-draft.docx").is_file())
        self.assertTrue(any(w.label == "Download draft Word" for w in app.get("download_button")))


if __name__ == "__main__":
    unittest.main()
