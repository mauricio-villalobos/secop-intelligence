from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path

from secop_intelligence.contracts import (
    DATASET_ID,
    ContractQuery,
    duplicate_contract_ids,
    fetch_contracts,
)


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch a privacy-minimized, bounded SECOP II contract sample."
    )
    parser.add_argument("--department", required=True)
    parser.add_argument("--signed-from", required=True, type=parse_date)
    parser.add_argument("--signed-before", required=True, type=parse_date)
    parser.add_argument("--limit", type=int, default=100)
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
        limit=args.limit,
    )
    records = fetch_contracts(query)
    duplicates = duplicate_contract_ids(records)
    if duplicates:
        duplicate_list = ", ".join(sorted(duplicates))
        raise RuntimeError(f"duplicate contract IDs received: {duplicate_list}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    records_path = args.output_dir / "contracts.jsonl"
    with records_path.open("w", encoding="utf-8", newline="\n") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            output.write("\n")

    manifest = {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat(),
        "dataset_id": DATASET_ID,
        "query": {
            "department": query.department,
            "signed_from": query.signed_from.isoformat(),
            "signed_before": query.signed_before.isoformat(),
            "limit": query.limit,
        },
        "record_count": len(records),
        "duplicates": 0,
        "records_file": records_path.name,
    }
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0
