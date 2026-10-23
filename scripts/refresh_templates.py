#!/usr/bin/env python3
"""Regenerate the public templates and guidance after editing sections.json."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "review_template"


def refresh():
    sections = json.loads((ROOT / "sections.json").read_text(encoding="utf-8"))
    for section in sections:
        report = ["# " + section["title"], ""]
        guidance = ["# Instructions: " + section["title"], "",
                    "Original source: `" + section["source_tex"] + "`.", "",
                    section["instructions"], ""]
        for field in section["fields"]:
            identifier, label = field["id"], field["label"]
            guidance.extend([f"## {identifier} — {label}", "", field["instructions"], ""])
            if field.get("group"):
                report.append("    " * field.get("depth", 0) + f"- **{label}:**")
                report.append("")
            elif section.get("prose"):
                report.extend([f"[[{identifier}]]", ""])
            else:
                report.append("    " * field.get("depth", 0) + f"- **{label}:** [[{identifier}]]")
                report.append("")
        for directory, lines in (("sections", report), ("guidance", guidance)):
            path = ROOT / directory / section["file"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    refresh()
