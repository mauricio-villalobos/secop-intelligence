from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime

import pytest

from secop_intelligence.review_export import build_review_artifact


def sample_record() -> dict[str, object]:
    return {
        "Contract ID": "CO1",
        "Entity": "Entidad",
        "State": "En ejecución",
        "Value (COP)": 1000,
        "Category": "Human review",
        "Attention lane": "Recent closure review",
        "Rule": "Active after contract end date",
        "Rule ID": "REVIEW_ACTIVE_AFTER_END_DATE",
        "Ruleset": "1.0",
        "Evidence": '{"as_of":"2026-07-23"}',
    }


def test_review_artifact_contains_reconciled_manifest_and_csv() -> None:
    payload = build_review_artifact(
        [sample_record()],
        filters={"lane": "CLOSURE_REVIEW", "category": "All"},
        generated_at=datetime(2026, 7, 23, 16, 0, tzinfo=UTC),
        displayed_limit=200,
    )

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert set(archive.namelist()) == {"findings.csv", "manifest.json"}
        csv_payload = archive.read("findings.csv")
        manifest = json.loads(archive.read("manifest.json"))

    rows = list(csv.DictReader(io.StringIO(csv_payload.decode("utf-8-sig"))))
    assert rows[0]["Contract ID"] == "CO1"
    assert rows[0]["Ruleset"] == "1.0"
    assert manifest["exported_row_count"] == 1
    assert manifest["displayed_limit"] == 200
    assert manifest["ruleset_versions"] == ["1.0"]
    assert manifest["findings_csv_sha256"] == hashlib.sha256(csv_payload).hexdigest()


def test_review_artifact_rejects_ambiguous_time_and_overflow() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        build_review_artifact(
            [],
            filters={},
            generated_at=datetime(2026, 7, 23),
            displayed_limit=200,
        )

    with pytest.raises(ValueError, match="exceeds"):
        build_review_artifact(
            [sample_record(), sample_record()],
            filters={},
            generated_at=datetime(2026, 7, 23, tzinfo=UTC),
            displayed_limit=1,
        )


def test_review_artifact_neutralizes_spreadsheet_formulas() -> None:
    record = sample_record()
    record["Entity"] = "=DANGEROUS()"
    payload = build_review_artifact(
        [record],
        filters={},
        generated_at=datetime(2026, 7, 23, tzinfo=UTC),
        displayed_limit=200,
    )

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        rows = list(
            csv.DictReader(
                io.StringIO(archive.read("findings.csv").decode("utf-8-sig"))
            )
        )

    assert rows[0]["Entity"] == "'=DANGEROUS()"
