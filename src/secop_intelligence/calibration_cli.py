from __future__ import annotations

import argparse
import json
from pathlib import Path

from secop_intelligence.calibration import build_calibration_profile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Profile rule prevalence and concentration without changing findings."
        )
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("data/warehouse/secop.duckdb"),
    )
    parser.add_argument("--top-entities", type=int, default=10)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    profile = build_calibration_profile(
        args.database,
        top_entities=args.top_entities,
    )
    payload = json.dumps(profile, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{payload}\n", encoding="utf-8")
    print(payload)
    return 0
