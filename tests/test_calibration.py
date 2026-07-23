from __future__ import annotations

from pathlib import Path

import pytest

from secop_intelligence.calibration import (
    CalibrationError,
    build_calibration_profile,
)
from secop_intelligence.warehouse import build_warehouse


def build_sample(database: Path) -> None:
    contracts = [
        {
            "id_contrato": "CO1",
            "nombre_entidad": "Entidad A",
            "departamento": "Valle del Cauca",
            "estado_contrato": "Modificado",
            "fecha_de_fin_del_contrato": "2026-07-01",
            "_content_sha256": "a" * 64,
        },
        {
            "id_contrato": "CO2",
            "nombre_entidad": "Entidad B",
            "departamento": "Valle del Cauca",
            "estado_contrato": "En ejecución",
            "fecha_de_fin_del_contrato": "2025-01-01",
            "_content_sha256": "b" * 64,
        },
        {
            "id_contrato": "CO3",
            "nombre_entidad": "Entidad B",
            "departamento": "Valle del Cauca",
            "estado_contrato": "Terminado",
            "_content_sha256": "c" * 64,
        },
    ]
    findings = [
        {
            "contract_id": "CO1",
            "rule_id": "REVIEW_ACTIVE_AFTER_END_DATE",
            "ruleset_version": "1.0",
            "category": "human_review",
            "evidence": {"as_of": "2026-07-23", "end_date": "2026-07-01"},
        },
        {
            "contract_id": "CO2",
            "rule_id": "REVIEW_ACTIVE_AFTER_END_DATE",
            "ruleset_version": "1.0",
            "category": "human_review",
            "evidence": {"as_of": "2026-07-23", "end_date": "2025-01-01"},
        },
        {
            "contract_id": "CO2",
            "rule_id": "REVIEW_EXTENSION_RECORDED",
            "ruleset_version": "1.0",
            "category": "human_review",
            "evidence": {},
        },
    ]
    build_warehouse(database, contracts, [], findings)


def test_calibration_profile_is_descriptive_and_reconciles(tmp_path: Path) -> None:
    database = tmp_path / "secop.duckdb"
    build_sample(database)

    profile = build_calibration_profile(database, top_entities=1)

    assert profile["result"] == "PASS"
    assert profile["flagged_contract_count"] == 2
    assert profile["flagged_contract_prevalence"] == 0.666667
    assert sum(item["finding_count"] for item in profile["rules"]) == 3
    assert {
        (item["contract_state"], item["finding_count"])
        for item in profile["by_state"]
        if item["rule_id"] == "REVIEW_ACTIVE_AFTER_END_DATE"
    } == {("Modificado", 1), ("En ejecución", 1)}
    assert len(profile["top_entities_per_rule"]) == 2
    assert {
        (
            item["contract_state"],
            item["overdue_bucket"],
            item["has_extension_finding"],
        )
        for item in profile["active_after_end_profile"]
    } == {
        ("Modificado", "01-30 days", False),
        ("En ejecución", "366+ days", True),
    }
    assert profile["reconciliation"] == {
        "rule_findings_equal_state_findings": True,
        "active_after_end_profile_total": 2,
        "active_after_end_rule_total": 2,
    }
    assert "no score" in profile["interpretation_guardrail"]


def test_calibration_rejects_missing_database(tmp_path: Path) -> None:
    with pytest.raises(CalibrationError, match="database not found"):
        build_calibration_profile(tmp_path / "missing.duckdb")


def test_calibration_rejects_invalid_entity_limit(tmp_path: Path) -> None:
    database = tmp_path / "secop.duckdb"
    build_sample(database)

    with pytest.raises(ValueError, match="top_entities"):
        build_calibration_profile(database, top_entities=0)
