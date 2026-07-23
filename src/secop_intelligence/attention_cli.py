from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from secop_intelligence.attention import (
    RULESET_VERSION,
    conflict_findings,
    evaluate_contract,
)
from secop_intelligence.privacy import load_jsonl


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from error


def load_json(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(
        isinstance(item, dict) for item in payload
    ):
        raise ValueError(f"{path} must contain a JSON array of objects")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a deterministic, evidence-bearing attention queue."
    )
    parser.add_argument("--as-of", required=True, type=parse_date)
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
        "--modification-conflicts",
        type=Path,
        default=Path("data/raw/modifications-conflicts.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/curated"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contracts = load_jsonl(args.contracts)
    modifications = load_jsonl(args.modifications)
    conflicts = load_json(args.modification_conflicts)

    modifications_by_contract: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for modification in modifications:
        modifications_by_contract[str(modification["id_contrato"])].append(modification)

    findings: list[dict[str, Any]] = []
    for contract in contracts:
        findings.extend(
            evaluate_contract(
                contract,
                modifications_by_contract[str(contract["id_contrato"])],
                as_of=args.as_of,
            )
        )
    findings.extend(conflict_findings(conflicts))
    findings.sort(key=lambda item: (item["contract_id"], item["rule_id"]))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    queue_path = args.output_dir / "attention-queue.jsonl"
    with queue_path.open("w", encoding="utf-8", newline="\n") as output:
        for item in findings:
            output.write(json.dumps(item, ensure_ascii=False, sort_keys=True))
            output.write("\n")

    rule_counts = Counter(item["rule_id"] for item in findings)
    category_counts = Counter(item["category"] for item in findings)
    manifest = {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat(),
        "ruleset_version": RULESET_VERSION,
        "as_of": args.as_of.isoformat(),
        "contract_count": len(contracts),
        "curated_modification_count": len(modifications),
        "quarantined_modification_versions": len(conflicts),
        "finding_count": len(findings),
        "rule_counts": dict(sorted(rule_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "queue_file": queue_path.name,
    }
    manifest_path = args.output_dir / "attention-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0
