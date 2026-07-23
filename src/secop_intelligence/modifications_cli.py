from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from secop_intelligence.modifications import (
    DATASET_ID,
    deduplicate_modifications,
    fetch_modifications_batched,
    orphan_contract_ids,
)
from secop_intelligence.privacy import load_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch modifications linked to a bounded contract cohort."
    )
    parser.add_argument(
        "--contracts",
        type=Path,
        default=Path("data/raw/contracts.jsonl"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw"),
    )
    parser.add_argument("--batch-size", type=int, default=150)
    parser.add_argument("--page-size", type=int, default=1000)
    return parser.parse_args()


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            output.write("\n")


def main() -> int:
    args = parse_args()
    contracts = load_jsonl(args.contracts)
    contract_ids = {str(contract["id_contrato"]) for contract in contracts}
    if not contract_ids:
        raise ValueError("contract sample must not be empty")

    source_records, completeness = fetch_modifications_batched(
        sorted(contract_ids),
        batch_size=args.batch_size,
        page_size=args.page_size,
    )
    records, duplicate_count, conflicts = deduplicate_modifications(source_records)
    orphans = orphan_contract_ids(records, contract_ids)
    if orphans:
        raise RuntimeError(f"orphan contract IDs received: {len(orphans)}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    records_path = args.output_dir / "modifications.jsonl"
    pending_records_path = records_path.with_suffix(".jsonl.pending")
    write_jsonl(pending_records_path, records)
    pending_records_path.replace(records_path)

    conflicts_path = args.output_dir / "modifications-conflicts.json"
    pending_conflicts_path = conflicts_path.with_suffix(".json.pending")
    pending_conflicts_path.write_text(
        json.dumps(conflicts, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    pending_conflicts_path.replace(conflicts_path)

    manifest = {
        "schema_version": 2,
        "result": "PASS" if not conflicts else "REVIEW_REQUIRED",
        "captured_at": datetime.now(UTC).isoformat(),
        "dataset_id": DATASET_ID,
        "completeness": completeness,
        "input_contract_count": len(contract_ids),
        "source_record_count": len(source_records),
        "record_count": len(records),
        "exact_duplicates_removed": duplicate_count,
        "conflicting_logical_versions": len(conflicts),
        "orphan_contract_ids": 0,
        "records_file": records_path.name,
        "conflicts_file": conflicts_path.name,
    }
    manifest_path = args.output_dir / "modifications-manifest.json"
    pending_manifest_path = manifest_path.with_suffix(".json.pending")
    pending_manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    pending_manifest_path.replace(manifest_path)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if not conflicts else 2
