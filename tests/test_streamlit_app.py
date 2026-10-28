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

    def test_new_review_upload_pdf_prepare_and_invalid_response(self):
        app = self.start()
        app.text_input[0].input("Study review")
        app.text_input[1].input("Reviewer")
        self.button(app, "Create review").click().run()
        self.assert_clean(app)
        workspace = Path(app.session_state["workspace"])
        pdf = (ROOT / "review_report.pdf").read_bytes()
        app.file_uploader[0].set_value(("protocol.pdf", pdf, "application/pdf"))
        self.button(app, "Save documents").click().run()
        self.assert_clean(app)
        self.assertEqual(pdf, Path(sa.load(workspace)["sources"]["PROTOCOL"]["path"]).read_bytes())
        self.button(app, "Next: exchange with Elsa →").click().run()
        self.button(app, "Prepare instructions").click().run()
        self.assert_clean(app)
        self.assertTrue(app.code)
        downloads = app.get("download_button")
        self.assertTrue(any(d.label == "Download instructions" for d in downloads))
        app.file_uploader[0].set_value(("bad.json", b'{}', "application/json"))
        self.button(app, "Load response").click().run()
        self.assert_clean(app)
        self.assertTrue(app.error)
        self.assertEqual({}, sa.load(workspace)["imports"])

    def test_edit_navigate_reopen_and_approve_whole_section(self):
        app, workspace = self.demo()
        app.text_area[0].input("Reviewer edited primary objective").run()
        app.radio[0].set_value("Export").run()
        self.assert_clean(app)
        self.assertTrue(self.button(app, "Create final Word").disabled)
        app.radio[0].set_value("Review sections").run()
        self.assertEqual("Reviewer edited primary objective", app.text_area[0].value)
        self.button(app, "Approve section and continue →").click().run()
        self.assert_clean(app)
        self.assertEqual(4, app.session_state["section"])
        self.assertEqual(3, len(sa.load(workspace)["reviewed"]))
        reopened = self.start()
        reopened.selectbox(key="review_picker").set_value(str(workspace)).run()
        reopened.radio[0].set_value("Review sections").run()
        self.assert_clean(reopened)
        self.assertEqual("Reviewer edited primary objective", reopened.text_area[0].value)

    def test_load_response_again_does_not_duplicate_and_retains_edits(self):
        app, workspace = self.demo()
        app.text_area[0].input("Saved before reimport").run()
        app.radio[0].set_value("Exchange with Elsa").run()
        app.file_uploader[0].set_value(("response.json", (workspace / "simulated_elsa_response.json").read_bytes(), "application/json"))
        self.button(app, "Load response").click().run()
        self.assert_clean(app)
        self.assertEqual(16, len(sa.load(workspace)["candidates"]))
        self.assertEqual("Saved before reimport", app.text_area[0].value)

    def test_pdf_panel_receives_the_cited_page_and_local_pdf(self):
        workspace = ui.create_review("PDF panel", "Reviewer")
        pdf = (ROOT / "review_report.pdf").read_bytes()
        ui.store_source(workspace, "protocol.pdf", pdf, "protocol")
        request_id = ui.create_request(workspace, 0)
        payload = sa.read_json(ROOT / "examples/stage_a/elsa_pilot_response.json")
        payload["request_id"] = request_id
        for records in payload["fields"].values():
            for record in records:
                record["sources"][0]["pdf_page"] = 2
        ui.import_bytes(workspace, json.dumps(payload).encode())
        app = self.start()
        app.selectbox(key="review_picker").set_value(str(workspace)).run()
        app.radio[0].set_value("Review sections").run()
        self.button(app, "View source").click().run()
        self.assert_clean(app)
        self.assertEqual(2, app.number_input[0].value)
        component = app.get("component_instance")[0]
        args = json.loads(component.proto.json_args)
        self.assertEqual([2], args["pages_to_render"])
        self.assertTrue(args["binary"])
        self.assertTrue(args["render_text"])

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
