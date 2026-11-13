#!/usr/bin/env python3
"""Create a fictional pilot with a simulated Elsa response; approve nothing."""
import argparse
import copy
from pathlib import Path
import shutil

import review
import stage_a

ROOT = Path(__file__).resolve().parents[1]


def create(destination):
    review.initialize(destination)
    inputs = destination / "inputs"
    inputs.mkdir()
    for filename in ("protocol.md", "background.md"):
        shutil.copyfile(ROOT / "examples/stage_a/sources" / filename, inputs / filename)
    stage_a.register_source(destination, inputs / "protocol.md", "PROTOCOL", "protocol", "1.0", "2026-01-15")
    stage_a.register_source(destination, inputs / "background.md", "BACKGROUND_01", "background", "1.0", "2025-12-01")
    config = stage_a.read_json(destination / "review.json")
    config.update(submission="SYN-001 — FICTIONAL STAGE A PILOT", author="Fictional reviewer", date="2026-01-20")
    stage_a.write_json(destination / "review.json", config)
    request_id = stage_a.prepare(destination, "3,4,5")
    payload = copy.deepcopy(stage_a.read_json(ROOT / "examples/stage_a/elsa_pilot_response.json"))
    payload["request_id"] = request_id
    path = destination / "simulated_elsa_response.json"
    stage_a.write_json(path, payload)
    stage_a.import_response(destination, path)
    stage_a.verification_report(destination)
    print("This was a simulated export, not a call to Elsa. No fields were accepted.")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    try:
        create(args.workspace)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
