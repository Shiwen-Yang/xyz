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
                    fields={"OBJECTIVES.PRIMARY": [record("P1", excerpt)], "OBJECTIVES.OTHER": [record("S1", excerpt)]})

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
        app.text_area(key=f"paste:{workspace.name}").input("{}").run()
        self.button(app, "Load pasted JSON").click().run()
        self.assertTrue(app.error)
        self.assertEqual({}, sa.load(workspace)["imports"])

    def test_load_from_downloads_folder_lists_references_and_highlights(self):
        app, workspace = self.workspace_with_pdf()
        self.button(app, "Prepare prompt").click().run()
        request_id = svc_request(workspace)
        downloads = Path(self.temp.name) / "downloads"
        downloads.mkdir()
        (downloads / ui.elsa_filename(request_id)).write_text(json.dumps(self.objectives_payload(request_id)))
        app.text_input(key=f"folder:{workspace.name}").input(str(downloads)).run()
        self.button(app, "Load response from this folder").click().run()
        self.assert_clean(app)
        self.assertEqual(2, len(sa.load(workspace)["candidates"]))
        self.assertEqual(str(downloads), sa.read_json(workspace / "review.json")["ui_download_dir"])
        reference = next(b for b in app.button if b.key.startswith("ref:OBJECTIVES.PRIMARY"))
        reference.click().run()
        self.assert_clean(app)
        args = json.loads(app.get("component_instance")[-1].proto.json_args)
        self.assertEqual([1], args["pages_to_render"])
        self.assertTrue(args["annotations"])
        self.assertEqual(1, args["annotations"][0]["page"])

    def test_missing_download_reports_the_expected_file_name(self):
        app, workspace = self.workspace_with_pdf()
        self.button(app, "Prepare prompt").click().run()
        app.text_input(key=f"folder:{workspace.name}").input(self.temp.name).run()
        self.button(app, "Load response from this folder").click().run()
        self.assertIn(ui.elsa_filename(svc_request(workspace)), app.error[0].value)

    def test_other_sections_are_listed_but_not_yet_available(self):
        app, workspace = self.demo()
        app.radio[0].set_value("Review workspace").run()
        self.assert_clean(app)
        labels = [e.label for e in app.expander if e.label[0].isdigit()]
        self.assertEqual(13, len(labels))
        self.assertIn("3. Primary Objective(s)", labels)

    @unittest.skipUnless(os.environ.get("PANDOC") or shutil.which("pandoc"), "Set PANDOC for Word download control test")
    def test_word_generation_exposes_download_control(self):
        app, workspace = self.demo()
        app.radio[0].set_value("Export").run()
        pandoc = os.environ.get("PANDOC") or shutil.which("pandoc")
        next(w for w in app.text_input if w.label == "Pandoc executable (if not on PATH)").input(pandoc)
        self.button(app, "Remember Word setting").click().run()
        self.button(app, "Create draft Word").click().run()
        self.assert_clean(app)
        self.assertTrue((workspace / "exports/review-draft.docx").is_file())
        self.assertTrue(any(w.label == "Download draft Word" for w in app.get("download_button")))


if __name__ == "__main__":
    unittest.main()
