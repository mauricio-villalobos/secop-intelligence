from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

TEXT_FIELDS = ("descripcion_del_proceso",)

PATTERNS = {
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "phone_context": re.compile(
        r"\b(?:tel[eé]fono|celular|contacto|whatsapp)\D{0,15}\d{7,12}\b",
        re.I,
    ),
    "identifier_context": re.compile(
        r"\b(?:c[eé]dula|documento|identificaci[oó]n|nit)\D{0,15}\d{6,12}\b",
        re.I,
    ),
}


def audit_record(record: Mapping[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    record_hash = str(record.get("_content_sha256", "missing"))
    for field in TEXT_FIELDS:
        value = record.get(field)
        if not isinstance(value, str):
            continue
        for pattern_name, pattern in PATTERNS.items():
            if pattern.search(value):
                findings.append(
                    {
                        "record_hash": record_hash,
                        "field": field,
                        "pattern": pattern_name,
                    }
                )
    return findings


def audit_records(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    record_count = 0
    for record in records:
        record_count += 1
        findings.extend(audit_record(record))

    counts = Counter(finding["pattern"] for finding in findings)
    return {
        "schema_version": 1,
        "result": "PASS" if not findings else "REVIEW_REQUIRED",
        "records_scanned": record_count,
        "finding_count": len(findings),
        "finding_counts": dict(sorted(counts.items())),
        "findings": findings,
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSON on line {line_number}") from error
            if not isinstance(record, dict):
                raise ValueError(f"line {line_number} must contain a JSON object")
            records.append(record)
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit generated SECOP JSONL without printing source text."
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("data/raw/contracts.jsonl"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("data/raw/privacy-audit.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit_records(load_jsonl(args.input))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {key: value for key, value in report.items() if key != "findings"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if report["result"] == "PASS" else 2
