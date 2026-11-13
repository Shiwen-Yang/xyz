"""Excerpt location in PDFs; needs PyMuPDF from requirements-ui.txt."""
import importlib.util
from pathlib import Path
import sys
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


if __name__ == "__main__":
    unittest.main()
