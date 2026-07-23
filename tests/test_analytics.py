from __future__ import annotations

from pathlib import Path

import pytest

from secop_intelligence.analytics import (
    AnalyticsDatabaseError,
    filter_options,
    overview,
    present_queue,
    present_rule_counts,
    review_queue,
    rule_counts,
)
from secop_intelligence.warehouse import build_warehouse


def build_sample(database: Path) -> None:
    contracts = [
        {
            "id_contrato": "CO1",
            "nombre_entidad": "Entidad",
            "departamento": "Valle del Cauca",
            "estado_contrato": "En ejecución",
            "valor_del_contrato": "1000",
            "_content_sha256": "a" * 64,
        },
        {
            "id_contrato": "CO2",
            "nombre_entidad": "Otra entidad",
            "departamento": "Valle del Cauca",
            "estado_contrato": "Terminado",
            "valor_del_contrato": "500",
            "_content_sha256": "b" * 64,
        },
    ]
    findings = [
        {
            "contract_id": "CO1",
            "rule_id": "REVIEW_EXTENSION_RECORDED",
            "ruleset_version": "1.0",
            "category": "human_review",
            "evidence": {"days": 3},
        },
        {
            "contract_id": "CO1",
            "rule_id": "DQ_MODIFICATION_VERSION_CONFLICT",
            "ruleset_version": "1.0",
            "category": "data_quality",
            "evidence": {"version": 2},
        },
    ]
    build_warehouse(database, contracts, [], findings)


def test_overview_and_rule_counts(tmp_path: Path) -> None:
    database = tmp_path / "secop.duckdb"
    build_sample(database)

    assert overview(database) == {
        "contract_count": 2,
        "finding_count": 2,
        "data_quality_count": 1,
        "human_review_count": 1,
        "contracts_with_findings": 1,
    }
    assert len(rule_counts(database)) == 2


def test_filter_options_and_parameterized_queue(tmp_path: Path) -> None:
    database = tmp_path / "secop.duckdb"
    build_sample(database)

    options = filter_options(database)
    queue = review_queue(
        database,
        category="human_review",
        contract_state="En ejecución",
    )

    assert options["categories"] == ["All", "data_quality", "human_review"]
    assert len(queue) == 1
    assert queue[0]["rule_id"] == "REVIEW_EXTENSION_RECORDED"


def test_queue_rejects_invalid_limit(tmp_path: Path) -> None:
    database = tmp_path / "secop.duckdb"
    build_sample(database)

    with pytest.raises(ValueError, match="limit"):
        review_queue(database, limit=0)


def test_missing_database_has_actionable_error(tmp_path: Path) -> None:
    with pytest.raises(AnalyticsDatabaseError, match="database not found"):
        overview(tmp_path / "missing.duckdb")


def test_presentation_hides_internal_hash_and_labels_rules() -> None:
    queue = present_queue(
        [
            {
                "finding_id": "internal-hash",
                "contract_id": "CO1",
                "entity_name": "Entidad",
                "contract_state": "En ejecución",
                "contract_value": 1000,
                "category": "human_review",
                "rule_id": "REVIEW_EXTENSION_RECORDED",
                "ruleset_version": "1.0",
                "evidence": '{"days":3}',
            }
        ]
    )
    counts = present_rule_counts(
        [
            {
                "category": "human_review",
                "rule_id": "REVIEW_EXTENSION_RECORDED",
                "finding_count": 1,
            }
        ]
    )

    assert "finding_id" not in queue[0]
    assert queue[0]["Rule"] == "Extension recorded"
    assert counts[0]["Category"] == "Human review"
