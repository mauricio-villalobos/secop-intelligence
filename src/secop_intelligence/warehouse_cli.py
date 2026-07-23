from __future__ import annotations

import argparse
import json
from pathlib import Path

from secop_intelligence.privacy import load_jsonl
from secop_intelligence.warehouse import build_warehouse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the typed, local SECOP analytical warehouse."
    )
    parser.add_argument(
        "--contracts",
        type=Path,
        default=Path("data/raw/contracts.jsonl"),
    )
    parser.add_argument(
        "--modifications",
        type=Path,
        default=Path("data/raw/modifications.jsonl"),
    )
    parser.add_argument(
        "--findings",
        type=Path,
        default=Path("data/curated/attention-queue.jsonl"),
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("data/warehouse/secop.duckdb"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_warehouse(
        args.database,
        load_jsonl(args.contracts),
        load_jsonl(args.modifications),
        load_jsonl(args.findings),
    )
    manifest_path = args.database.with_name("warehouse-manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0
