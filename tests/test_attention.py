from datetime import date

from secop_intelligence.attention import (
    conflict_findings,
    evaluate_contract,
)


def contract(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id_contrato": "CO1.PCCNTR.1",
        "estado_contrato": "En ejecución",
        "fecha_de_inicio_del_contrato": "2026-01-01T00:00:00",
        "fecha_de_fin_del_contrato": "2026-12-31T00:00:00",
        "valor_del_contrato": "100",
        "valor_pagado": "50",
        "dias_adicionados": "0",
    }
    base.update(overrides)
    return base


def rule_ids(findings: list[dict[str, object]]) -> set[str]:
    return {str(item["rule_id"]) for item in findings}


def test_paid_value_above_contract_is_data_quality_finding() -> None:
    findings = evaluate_contract(
        contract(valor_pagado="101"),
        [],
        as_of=date(2026, 7, 23),
    )

    assert "DQ_PAID_EXCEEDS_CONTRACT_VALUE" in rule_ids(findings)


def test_end_before_start_is_data_quality_finding() -> None:
    findings = evaluate_contract(
        contract(
            fecha_de_inicio_del_contrato="2026-03-01T00:00:00",
            fecha_de_fin_del_contrato="2026-02-01T00:00:00",
        ),
        [],
        as_of=date(2026, 7, 23),
    )

    assert "DQ_END_BEFORE_START" in rule_ids(findings)


def test_active_contract_after_end_date_requires_review() -> None:
    findings = evaluate_contract(
        contract(fecha_de_fin_del_contrato="2026-07-01T00:00:00"),
        [],
        as_of=date(2026, 7, 23),
    )

    assert "REVIEW_ACTIVE_AFTER_END_DATE" in rule_ids(findings)


def test_active_contract_ending_within_30_days_requires_review() -> None:
    findings = evaluate_contract(
        contract(fecha_de_fin_del_contrato="2026-08-01T00:00:00"),
        [],
        as_of=date(2026, 7, 23),
    )

    assert "REVIEW_ENDING_WITHIN_30_DAYS" in rule_ids(findings)


def test_recorded_extension_requires_review() -> None:
    modifications = [{"dias_extendidos": "15"}]

    findings = evaluate_contract(
        contract(),
        modifications,
        as_of=date(2026, 7, 23),
    )

    assert "REVIEW_EXTENSION_RECORDED" in rule_ids(findings)


def test_quarantined_conflict_becomes_data_quality_finding() -> None:
    conflicts = [
        {
            "id_contrato": "CO1.PCCNTR.1",
            "identificador_modificacion": "CO1.CTRMOD.1",
            "numero_version": "9",
            "representations": 2,
            "differing_fields": ["dias_extendidos"],
        }
    ]

    findings = conflict_findings(conflicts)

    assert findings[0]["rule_id"] == "DQ_MODIFICATION_VERSION_CONFLICT"
    assert findings[0]["category"] == "data_quality"
