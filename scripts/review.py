#!/usr/bin/env python3
"""Offline Stage A review workspace CLI and Pandoc Word assembly."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import stage_a
from word_style import customize

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "review_template"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def initialize(destination):
    if destination.exists():
        raise ValueError(f"Destination already exists; nothing overwritten: {destination}")
    destination.mkdir(parents=True)
    shutil.copyfile(PACKAGE / "reviewer_checks.md", destination / "reviewer_checks.md")
    config = {
        "title": "Statistical Review and Evaluation for Pre-Licensure Submissions",
        "author": "OBPV/DB", "date": "", "submission": "[[SUBMISSION]]",
        "workflow": "stage-a", "workflow_version": 1,
    }
    write(destination / "review.json", json.dumps(config, indent=2) + "\n")
    stage_a.initialize(destination)
    print(f"Created {destination}. Register the current protocol with the source command, then prepare a request.")


def assemble(workspace):
    config = json.loads((workspace / "review.json").read_text(encoding="utf-8"))
    required = ("title", "author", "date", "submission")
    if any(not isinstance(config.get(key), str) for key in required):
        raise ValueError("review.json must contain string title, author, date, and submission values")
    if any(re.search(r"!\[|<\s*(?:img|iframe|script)\b", config[key], re.I) for key in required):
        raise ValueError("review.json: embedded media is unsupported in report metadata")
    if config.get("workflow") != "stage-a":
        raise ValueError("This workspace uses the legacy workflow; see legacy/README.md")
    return stage_a.assemble(workspace)


def build(args):
    config, body, issues = assemble(args.workspace)
    if args.final and issues:
        raise ValueError("Stage A final output requires reviewed fields and current sources; "
                         "--acknowledge-unresolved cannot bypass verification:\n" + "\n".join(issues))
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
    accepted_notes = stage_a.accepted_uncertainties(args.workspace)
    write(args.output.with_suffix(".checks.txt"),
          ("FINAL: reviewer approval acknowledged.\n" if args.final else "DRAFT: requires reviewer approval.\n") +
          ("Flagged-item disposition explicitly acknowledged.\n" if args.final and args.acknowledge_unresolved else "") +
          "Automated checks do not validate scientific accuracy, evidence completeness, or page layout.\n" +
          ("Flagged items:\n" + "\n".join(issues) if issues else "No unresolved verification markers.") + "\n" +
          ("Reviewer-accepted limits (not automatic verification):\n" + "\n".join(accepted_notes) + "\n" if accepted_notes else ""))
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
    init = commands.add_parser("init", help="Create a review workspace without overwriting files")
    init.add_argument("workspace", type=Path)
    source = commands.add_parser("source", help="Register a local document and its fingerprint")
    source.add_argument("workspace", type=Path)
    source.add_argument("path", type=Path)
    source.add_argument("--id", required=True)
    source.add_argument("--role", choices=["protocol", "background"], required=True)
    source.add_argument("--version", required=True)
    source.add_argument("--date", required=True)
    source.add_argument("--pages", type=int)
    prepare = commands.add_parser("prepare", help="Generate an Elsa request, response schema, and manifest")
    prepare.add_argument("workspace", type=Path)
    prepare.add_argument("--sections", default="3,4,5")
    prepare.add_argument("--fields")
    prepare.add_argument("--sources", help="Comma-separated registered source IDs; default: all")
    importer = commands.add_parser("import", help="Validate an Elsa export and stage candidates")
    importer.add_argument("workspace", type=Path)
    importer.add_argument("json_file", type=Path)
    verifier = commands.add_parser("review", help="Generate verification report or explicitly decide a field")
    verifier.add_argument("workspace", type=Path)
    target = verifier.add_mutually_exclusive_group()
    target.add_argument("--candidate")
    target.add_argument("--manual")
    decision = verifier.add_mutually_exclusive_group()
    decision.add_argument("--accept", dest="action", action="store_const", const="accept")
    decision.add_argument("--reject", dest="action", action="store_const", const="reject")
    verifier.add_argument("--reviewer")
    verifier.add_argument("--reason", default="")
    verifier.add_argument("--exclude", action="store_true", help="Record accepted text/disposition but omit it from the memo")
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
        elif args.command == "source":
            stage_a.register_source(args.workspace, args.path, args.id, args.role, args.version, args.date, args.pages)
        elif args.command == "prepare":
            stage_a.prepare(args.workspace, args.sections, args.fields, args.sources)
        elif args.command == "import":
            stage_a.import_response(args.workspace, args.json_file)
        elif args.command == "review":
            stage_a.review_item(args.workspace, args.candidate, args.manual, args.action, args.reviewer, args.reason, args.exclude)
        else:
            build(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
