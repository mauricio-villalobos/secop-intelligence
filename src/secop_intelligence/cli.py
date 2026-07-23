from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path

from secop_intelligence.contracts import (
    DATASET_ID,
    ContractQuery,
    fetch_complete_contracts,
)


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch a complete, privacy-minimized SECOP II contract slice."
    )
    parser.add_argument("--department", required=True)
    parser.add_argument("--signed-from", required=True, type=parse_date)
    parser.add_argument("--signed-before", required=True, type=parse_date)
    parser.add_argument(
        "--max-records",
        "--limit",
        dest="max_records",
        type=int,
        default=60_000,
    )
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    query = ContractQuery(
        department=args.department,
        signed_from=args.signed_from,
        signed_before=args.signed_before,
        limit=args.max_records,
        page_size=args.page_size,
    )
    records, completeness = fetch_complete_contracts(query)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    records_path = args.output_dir / "contracts.jsonl"
    pending_records_path = records_path.with_suffix(".jsonl.pending")
    with pending_records_path.open("w", encoding="utf-8", newline="\n") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            output.write("\n")
    pending_records_path.replace(records_path)

    manifest = {
        "schema_version": 2,
        "captured_at": datetime.now(UTC).isoformat(),
        "dataset_id": DATASET_ID,
        "query": {
            "department": query.department,
            "signed_from": query.signed_from.isoformat(),
            "signed_before": query.signed_before.isoformat(),
            "max_records": query.limit,
            "page_size": query.page_size,
        },
        "completeness": completeness,
        "record_count": completeness["record_count"],
        "duplicates": 0,
        "records_file": records_path.name,
    }
    manifest_path = args.output_dir / "manifest.json"
    pending_manifest_path = manifest_path.with_suffix(".json.pending")
    pending_manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    pending_manifest_path.replace(manifest_path)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0
