#!/usr/bin/env python3
"""Legacy section-based Markdown review workflow (init, bundle, build). Superseded by Stage A.

Run from the repository root: python3 legacy/scripts/review_legacy.py init reviews/my-review
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from word_style import customize  # noqa: E402

LEGACY = ROOT / "legacy" / "review_template"   # guidance, prompts, blank sections, logs
PACKAGE = ROOT / "review_template"              # shared: sections.json, reference.docx, reviewer_checks.md


def catalog():
    return json.loads((PACKAGE / "sections.json").read_text(encoding="utf-8"))


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def initialize(destination):
    if destination.exists():
        raise ValueError(f"Destination already exists; nothing overwritten: {destination}")
    destination.mkdir(parents=True)
    shutil.copytree(LEGACY / "sections", destination / "sections")
    for name in ("documents.md", "evidence.md", "issues.md"):
        shutil.copyfile(LEGACY / name, destination / name)
    shutil.copyfile(PACKAGE / "reviewer_checks.md", destination / "reviewer_checks.md")
    config = {
        "title": "Statistical Review and Evaluation for Pre-Licensure Submissions",
        "author": "OBPV/DB", "date": "", "submission": "[[SUBMISSION]]"
    }
    write(destination / "review.json", json.dumps(config, indent=2) + "\n")
    print(f"Created {destination}. Fill documents.md, then use the intake and section prompts.")


def selected_sections(selection):
    sections = catalog()
    if selection == "all":
        return sections
    try:
        requested = {int(value.strip()) for value in selection.split(",")}
    except ValueError as exc:
        raise ValueError("Sections must be 'all' or comma-separated numbers, e.g. 3,4,5") from exc
    if not requested or not requested <= {s["number"] for s in sections}:
        raise ValueError("Section numbers must be between 1 and 13")
    return [s for s in sections if s["number"] in requested]


def bundle(workspace, selection, output):
    parts = [(LEGACY / "instructions.md").read_text(encoding="utf-8")]
    parts.append("# Source register\n\n" + (workspace / "documents.md").read_text(encoding="utf-8"))
    for section in selected_sections(selection):
        parts.append((LEGACY / "guidance" / section["file"]).read_text(encoding="utf-8"))
        parts.append("## Current section draft\n\n" +
                     (workspace / "sections" / section["file"]).read_text(encoding="utf-8"))
    parts.append("# Task\n\n" + (LEGACY / "prompts" / "02_extract_sections.md").read_text(encoding="utf-8"))
    write(output, "\n\n---\n\n".join(parts) + "\n")
    print(f"Wrote {output}. Upload/paste this with the selected approved source documents.")


def assemble(workspace):
    config = json.loads((workspace / "review.json").read_text(encoding="utf-8"))
    required = ("title", "author", "date", "submission")
    if any(not isinstance(config.get(key), str) for key in required):
        raise ValueError("review.json must contain string title, author, date, and submission values")
    if any(re.search(r"!\[|<\s*(?:img|iframe|script)\b", config[key], re.I) for key in required):
        raise ValueError("review.json: embedded media is unsupported in report metadata")
    parts, issues = [], []
    for section in catalog():
        path = workspace / "sections" / section["file"]
        text = path.read_text(encoding="utf-8").strip()
        lines = text.splitlines()
        expected = "# " + section["title"]
        if not lines or lines[0] != expected:
            raise ValueError(f"{path}: first line must be {expected!r}")
        if re.search(r"^#\s", "\n".join(lines[1:]), re.M):
            raise ValueError(f"{path}: use ## or ### for subsections; only one # heading is allowed")
        if not "\n".join(lines[1:]).strip():
            raise ValueError(f"{path}: empty section; provide text or a reviewer-approved disposition")
        if re.search(r"<!--|```|~~~|^---\s*$", text, re.M):
            raise ValueError(f"{path}: remove comments, code fences, front matter, or separators")
        if re.search(r"!\[|<\s*(?:img|iframe|script)\b|\{=", text, re.I):
            raise ValueError(f"{path}: embedded media/raw blocks are unsupported; add figures in Word")
        for number, line in enumerate(lines, 1):
            if re.search(r"\[\[.*?\]\]|\b(?:TODO|TBD)\b|not located|not applicable|conflicting|reviewer input required|pending reviewer verification|potential concern|unapproved", line, re.I):
                issues.append(f"{section['file']}:{number}: {line.strip()}")
        parts.append(text)
    for key in required:
        if re.search(r"\[\[.*?\]\]", config[key]):
            issues.append(f"review.json: unresolved {key}")
    return config, "\n\n".join(parts) + "\n", issues


def build(args):
    config, body, issues = assemble(args.workspace)
    if args.final and not args.reviewer_approved:
        raise ValueError("Final output requires --reviewer-approved after scientific and evidence review")
    if args.final and re.search(r"\[\[.*?\]\]|\b(?:TODO|TBD)\b", body + json.dumps(config), re.I):
        raise ValueError("Final output contains unfilled placeholders; resolve them first")
    if args.final and issues and not args.acknowledge_unresolved:
        raise ValueError("Final output has flagged items. Resolve them or explicitly use "
                         "--acknowledge-unresolved after review:\n" + "\n".join(issues))
    if args.output.suffix.lower() not in {".docx", ".md"}:
        raise ValueError("--output must end in .docx or .md")
    # Use explicit JSON metadata as a YAML subset; do not interpolate user text into YAML or shell code.
    metadata = dict(config)
    metadata["title"] = ("" if args.final else "DRAFT — ") + config["title"]
    metadata["subtitle"] = config["submission"]
    markdown = "---\n" + json.dumps(metadata, ensure_ascii=False) + "\n---\n\n" + body
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.suffix.lower() == ".docx":
        build_word(args, markdown)
    write(args.output.with_suffix(".md"), markdown)
    write(args.output.with_suffix(".checks.txt"),
          ("FINAL: reviewer approval acknowledged.\n" if args.final else "DRAFT: requires reviewer approval.\n") +
          ("Flagged-item disposition explicitly acknowledged.\n" if args.final and args.acknowledge_unresolved else "") +
          "Automated checks do not validate scientific accuracy, evidence completeness, or page layout.\n" +
          ("Flagged items:\n" + "\n".join(issues) if issues else "No unresolved verification markers.") + "\n" +
          "")
    print(f"Wrote {args.output}; Markdown and check log saved alongside it.")
    if issues:
        print(f"Flagged {len(issues)} item(s); see {args.output.with_suffix('.checks.txt')}")


def build_word(args, markdown):
    pandoc = shutil.which(args.pandoc)
    if not pandoc:
        raise ValueError("Pandoc was not found. Install Pandoc locally or pass --pandoc /path/to/pandoc; use .md output without Pandoc")
    with tempfile.TemporaryDirectory(prefix="review-build-") as directory:
        temporary = Path(directory)
        source = temporary / "report.md"
        write(source, markdown)
        reference = args.reference_doc or PACKAGE / "reference.docx"
        if not reference.exists():
            raise ValueError(f"Reference document not found: {reference}")
        generated = temporary / "report.docx"
        subprocess.run([pandoc, str(source), "--from=markdown-raw_html-raw_tex",
                        "--to=docx", "--standalone", "--fail-if-warnings",
                        f"--reference-doc={reference.resolve()}", "--output", str(generated)],
                       check=True)
        customize(generated, args.output, reference=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create a legacy review workspace without overwriting files")
    init.add_argument("workspace", type=Path)
    pack = commands.add_parser("bundle", help="Package instructions and selected sections for chat")
    pack.add_argument("workspace", type=Path)
    pack.add_argument("--sections", default="all")
    pack.add_argument("--output", type=Path, required=True)
    render = commands.add_parser("build", help="Assemble the 13 sections and generate Word locally")
    render.add_argument("workspace", type=Path)
    render.add_argument("--output", type=Path, required=True)
    render.add_argument("--pandoc", default="pandoc")
    render.add_argument("--reference-doc", type=Path)
    render.add_argument("--final", action="store_true")
    render.add_argument("--reviewer-approved", action="store_true")
    render.add_argument("--acknowledge-unresolved", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "init":
            initialize(args.workspace)
        elif args.command == "bundle":
            bundle(args.workspace, args.sections, args.output)
        else:
            build(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
