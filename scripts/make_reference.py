#!/usr/bin/env python3
"""Rebuild the checked-in Word reference using a local Pandoc installation."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

from word_style import customize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pandoc", default="pandoc")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] /
                        "review_template" / "reference.docx")
    args = parser.parse_args()
    binary = shutil.which(args.pandoc)
    if not binary:
        parser.error("Pandoc was not found; install it or pass --pandoc /path/to/pandoc")
    with tempfile.TemporaryDirectory(prefix="review-reference-") as directory:
        source = Path(directory) / "default.docx"
        source.write_bytes(subprocess.check_output([binary, "--print-default-data-file=reference.docx"]))
        customize(source, args.output, reference=True)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
