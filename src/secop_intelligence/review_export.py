from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

EXPORT_FIELDS = (
    "Contract ID",
    "Entity",
    "State",
    "Value (COP)",
    "Category",
    "Attention lane",
    "Rule",
    "Rule ID",
    "Ruleset",
    "Evidence",
)


def _safe_csv_value(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{value}"
    return value


def _csv_bytes(records: Sequence[Mapping[str, Any]]) -> bytes:
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=EXPORT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        writer.writerow(
            {field: _safe_csv_value(record.get(field)) for field in EXPORT_FIELDS}
        )
    return text.getvalue().encode("utf-8-sig")


def build_review_artifact(
    records: Sequence[Mapping[str, Any]],
    *,
    filters: Mapping[str, str],
    generated_at: datetime,
    displayed_limit: int,
) -> bytes:
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    if not 1 <= displayed_limit <= 1000:
        raise ValueError("displayed_limit must be between 1 and 1000")
    if len(records) > displayed_limit:
        raise ValueError("record count exceeds displayed_limit")

    csv_payload = _csv_bytes(records)
    manifest = {
        "schema_version": 1,
        "artifact_type": "displayed_review_queue",
        "generated_at": generated_at.isoformat(),
        "displayed_limit": displayed_limit,
        "exported_row_count": len(records),
        "filters": dict(sorted(filters.items())),
        "ruleset_versions": sorted(
            {
                str(record["Ruleset"])
                for record in records
                if record.get("Ruleset") not in (None, "")
            }
        ),
        "findings_csv_sha256": hashlib.sha256(csv_payload).hexdigest(),
        "completeness_notice": (
            "This artifact contains the currently displayed, bounded queue. "
            "It is not a complete export when exported_row_count equals "
            "displayed_limit."
        ),
        "guardrail": (
            "Findings support human review and are not allegations, legal "
            "conclusions, risk scores, or automated decisions."
        ),
    }
    manifest_payload = (
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()

    output = io.BytesIO()
    with zipfile.ZipFile(
        output,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr("findings.csv", csv_payload)
        archive.writestr("manifest.json", manifest_payload)
    return output.getvalue()
