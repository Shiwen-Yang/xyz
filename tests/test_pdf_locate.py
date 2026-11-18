"""Excerpt location in PDFs; needs PyMuPDF from requirements-ui.txt."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import pdf_locate

PDF = ROOT / "tests/fixtures/sample.pdf"


@unittest.skipUnless(importlib.util.find_spec("pymupdf"), "Install requirements-ui.txt for PDF highlighting tests")
class LocateTests(unittest.TestCase):
    def test_exact_match_on_cited_page_returns_rectangles(self):
        found = pdf_locate.locate(PDF, 1, "Statistical Review and Evaluation for Pre-Licensure Submissions")
        self.assertEqual(("exact", 1), (found["status"], found["page"]))
        self.assertTrue(found["rects"])

    def test_whitespace_and_line_breaks_are_ignored(self):
        found = pdf_locate.locate(PDF, 1, "Executive Summary:\n  Background:\nPrimary Objective(s):")
        self.assertEqual("exact", found["status"])

    def test_wrong_cited_page_is_reported_not_trusted(self):
        found = pdf_locate.locate(PDF, 2, "Statistical Review and Evaluation")
        self.assertEqual(("other_page", 1), (found["status"], found["page"]))

    def test_missing_text_and_non_pdf_are_not_highlighted(self):
        self.assertEqual("not_found", pdf_locate.locate(PDF, 1, "this sentence is nowhere in the sample document")["status"])
        self.assertEqual("unavailable", pdf_locate.locate(ROOT / "README.md", 1, "Protocol Review")["status"])

    def make_pdf(self, text):
        import pymupdf
        path = Path(tempfile.mkdtemp()) / "t.pdf"
        document = pymupdf.open()
        document.new_page().insert_textbox(pymupdf.Rect(72, 72, 300, 300), text, fontsize=11)
        document.save(str(path))
        return path

    def test_hyphenated_multiline_passage_is_one_box_with_start_and_end_marks(self):
        path = self.make_pdf("The primary objective is to evaluate the efficacy of the vaccine in prevent-\ning confirmed disease among adults aged 18 to 65 years. More padding text follows here.")
        found = pdf_locate.locate(path, 1, "The primary objective is to evaluate the efficacy of the vaccine in preventing confirmed disease among adults aged 18 to 65 years.")
        self.assertEqual("exact", found["status"])
        self.assertEqual(1, len(found["rects"]))  # not one piece per line
        self.assertEqual(2, len(found["marks"]))  # first and last word

    def test_changed_wording_still_boxes_the_whole_span_as_partial(self):
        path = self.make_pdf("The primary objective is to evaluate the efficacy of the vaccine in preventing confirmed disease among adults aged 18 to 65 years. More padding text follows here.")
        found = pdf_locate.locate(path, 1, "The primary objective is to evaluate the effectiveness of the vaccine in preventing confirmed disease among adults aged 18 to 65 years.")
        self.assertEqual("partial", found["status"])
        self.assertEqual(1, len(found["rects"]))


if __name__ == "__main__":
    unittest.main()
