"""Behavior checks for report validation and real Pandoc/Word conversion."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "legacy" / "scripts"))
import review_legacy as review
from word_style import customize, tag

PANDOC = os.environ.get("PANDOC") or shutil.which("pandoc")


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.workspace = self.directory / "review"
        shutil.copytree(ROOT / "legacy" / "examples" / "synthetic_review", self.workspace)

    def args(self, **overrides):
        values = dict(workspace=self.workspace, output=self.directory / "report.docx",
                      pandoc=PANDOC or "missing-pandoc-executable", reference_doc=None,
                      final=False, reviewer_approved=False, acknowledge_unresolved=False)
        values.update(overrides)
        return SimpleNamespace(**values)

    def section(self, number):
        section = review.catalog()[number - 1]
        return self.workspace / "sections" / section["file"]

    def test_init_preserves_existing_folder(self):
        target = self.directory / "new"
        with contextlib.redirect_stdout(io.StringIO()):
            review.initialize(target)
        self.assertEqual(13, len(list((target / "sections").glob("*.md"))))
        self.assertIn("[[DESIGN.ALLOCATION_RATIO]]", (target / "sections" / "04_design_features.md").read_text())
        with self.assertRaisesRegex(ValueError, "already exists"):
            review.initialize(target)

    def test_explicit_numeric_order_and_excluded_guidance(self):
        _, body, issues = review.assemble(self.workspace)
        headings = [line[2:] for line in body.splitlines() if line.startswith("# ")]
        self.assertEqual([s["title"] for s in review.catalog()], headings)
        self.assertNotIn("Instructions for the review assistant", body)
        self.assertNotIn("Supporting excerpt", body)
        self.assertTrue(any("Pending reviewer verification" in issue for issue in issues))

    def test_missing_section_stops_assembly(self):
        self.section(8).unlink()
        with self.assertRaises(FileNotFoundError):
            review.assemble(self.workspace)

    def test_wrong_or_duplicate_top_heading_is_rejected(self):
        self.section(3).write_text("# Wrong heading\n\ntext\n")
        with self.assertRaisesRegex(ValueError, "first line"):
            review.assemble(self.workspace)
        self.section(3).write_text("# Primary Objective(s):\n\ntext\n\n# Extra section\n")
        with self.assertRaisesRegex(ValueError, "only one"):
            review.assemble(self.workspace)

    def test_chat_wrappers_and_remote_media_are_rejected(self):
        path = self.section(3)
        for text in ("```markdown\ntext\n```", "<!-- instructions -->\ntext",
                     "![diagram](https://example.invalid/image.png)"):
            path.write_text("# Primary Objective(s):\n\n" + text)
            with self.assertRaises(ValueError):
                review.assemble(self.workspace)

    def test_final_requires_approval_and_disposition(self):
        with self.assertRaisesRegex(ValueError, "reviewer-approved"):
            review.build(self.args(final=True))
        with self.assertRaisesRegex(ValueError, "flagged items"):
            review.build(self.args(final=True, reviewer_approved=True))

    def test_acknowledgment_cannot_bypass_placeholders(self):
        path = self.section(3)
        path.write_text(path.read_text() + "\n[[UNFILLED]]\n")
        with self.assertRaisesRegex(ValueError, "unfilled placeholders"):
            review.build(self.args(final=True, reviewer_approved=True, acknowledge_unresolved=True))

    def test_metadata_placeholder_blocks_final(self):
        path = self.workspace / "review.json"
        config = json.loads(path.read_text())
        config["submission"] = "[[SUBMISSION]]"
        path.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, "unfilled placeholders"):
            review.build(self.args(final=True, reviewer_approved=True, acknowledge_unresolved=True))

    def test_bundle_contains_selected_guidance_and_source_register(self):
        output = self.directory / "chat.md"
        with contextlib.redirect_stdout(io.StringIO()):
            review.bundle(self.workspace, "3,4,5", output)
        text = output.read_text()
        self.assertIn("Instructions for the review assistant", text)
        self.assertIn("DESIGN.ALLOCATION_RATIO", text)
        self.assertIn("SYN-001", text)
        self.assertNotIn("## SAMPLE_SIZE.VERIFICATION", text)
        with self.assertRaises(ValueError):
            review.selected_sections("0,14")

    def test_single_arm_no_interim_and_medical_sizing_variants(self):
        self.section(4).write_text("# Design Features:\n\n- **Study population:** Adults with condition Q.\n\n- **Treatment Allocation and Randomization:** Single arm; Product A, 1 unit orally daily.\n")
        self.section(9).write_text("# Interim Analyses:\n\nNone.\n")
        self.section(10).write_text("# Sample Size Estimation:\n\n- **Number of subjects to be accrued/evaluated:** 20; medical feasibility basis confirmed by reviewer.\n")
        _, text, _ = review.assemble(self.workspace)
        self.assertNotIn("**allocation ratio:**", text)
        self.assertNotIn("**Power:**", text)
        self.assertIn("Single arm; Product A", text)
        self.assertIn("# Interim Analyses:\n\nNone.", text)

    def test_coverage_of_original_sections_and_guidance(self):
        sections = review.catalog()
        self.assertEqual(list(range(1, 14)), [s["number"] for s in sections])
        identifiers = [f["id"] for s in sections for f in s["fields"]]
        self.assertEqual(len(set(identifiers)), len(identifiers))
        for section in sections:
            self.assertTrue((ROOT / section["source_tex"]).exists())
            guidance = (review.LEGACY / "guidance" / section["file"]).read_text()
            for field in section["fields"]:
                self.assertIn(field["id"], guidance)
                self.assertTrue(field["instructions"])

    @unittest.skipUnless(PANDOC, "Pandoc unavailable; set PANDOC for integration checks")
    def test_word_output_has_native_lists_math_tables_and_geometry(self):
        args = self.args()
        with contextlib.redirect_stdout(io.StringIO()):
            review.build(args)
        with ZipFile(args.output) as archive:
            for name in archive.namelist():
                if name.endswith(".xml"):
                    ET.fromstring(archive.read(name))
            document = ET.fromstring(archive.read("word/document.xml"))
            text = " ".join(e.text or "" for e in document.iter(tag("t")))
            self.assertIn("DRAFT", text)
            self.assertNotIn("Supporting excerpt", text)
            self.assertNotIn("[[", text)
            self.assertTrue(list(document.iter(tag("numPr"))))
            math = document.findall(".//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath")
            self.assertGreaterEqual(len(math), 4)
            tables = list(document.iter(tag("tbl")))
            self.assertEqual(1, len(tables))
            table = tables[0]
            widths = [int(e.get(tag("w"))) for e in table.find(tag("tblGrid"))]
            self.assertEqual(9360, sum(widths))
            self.assertEqual("9360", table.find(tag("tblPr")).find(tag("tblW")).get(tag("w")))
            self.assertEqual("120", table.find(tag("tblPr")).find(tag("tblInd")).get(tag("w")))
            for row in table.findall(tag("tr")):
                self.assertEqual(widths, [int(cell.find(tag("tcPr")).find(tag("tcW")).get(tag("w"))) for cell in row.findall(tag("tc"))])
            self.assertIsNotNone(table.find(tag("tr")).find(tag("trPr")).find(tag("tblHeader")))
            section = next(document.iter(tag("sectPr")))
            self.assertEqual("12240", section.find(tag("pgSz")).get(tag("w")))
            self.assertEqual("1440", section.find(tag("pgMar")).get(tag("left")))
        self.assertTrue(args.output.with_suffix(".md").exists())
        self.assertIn("Pending reviewer verification", args.output.with_suffix(".checks.txt").read_text())

    @unittest.skipUnless(PANDOC, "Pandoc unavailable; set PANDOC for integration checks")
    def test_final_with_explicit_acknowledgment(self):
        args = self.args(final=True, reviewer_approved=True, acknowledge_unresolved=True)
        with contextlib.redirect_stdout(io.StringIO()):
            review.build(args)
        self.assertNotIn("DRAFT", args.output.with_suffix(".md").read_text())
        self.assertIn("reviewer approval acknowledged", args.output.with_suffix(".checks.txt").read_text())


if __name__ == "__main__":
    unittest.main()
