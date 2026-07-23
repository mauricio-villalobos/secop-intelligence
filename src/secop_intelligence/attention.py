from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

RULESET_VERSION = "1.0"
ACTIVE_STATES = frozenset({"en ejecución", "modificado"})


class AttentionDataError(ValueError):
    """Raised when a deterministic rule cannot safely interpret source data."""


def parse_date(value: Any, field: str) -> date | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError as error:
        raise AttentionDataError(f"invalid date in {field}") from error


def parse_decimal(value: Any, field: str) -> Decimal:
    if value in (None, ""):
        return Decimal(0)
    try:
        return Decimal(str(value))
    except InvalidOperation as error:
        raise AttentionDataError(f"invalid decimal in {field}") from error


def finding(
    *,
    contract_id: str,
    rule_id: str,
    category: str,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "contract_id": contract_id,
        "rule_id": rule_id,
        "ruleset_version": RULESET_VERSION,
        "category": category,
        "evidence": dict(evidence),
    }


def evaluate_contract(
    contract: Mapping[str, Any],
    modifications: Iterable[Mapping[str, Any]],
    *,
    as_of: date,
) -> list[dict[str, Any]]:
    contract_id = str(contract["id_contrato"])
    results: list[dict[str, Any]] = []
    start_date = parse_date(
        contract.get("fecha_de_inicio_del_contrato"),
        "fecha_de_inicio_del_contrato",
    )
    end_date = parse_date(
        contract.get("fecha_de_fin_del_contrato"),
        "fecha_de_fin_del_contrato",
    )
    state = str(contract.get("estado_contrato", "")).strip().lower()
    contract_value = parse_decimal(
        contract.get("valor_del_contrato"),
        "valor_del_contrato",
    )
    paid_value = parse_decimal(contract.get("valor_pagado"), "valor_pagado")

    if start_date and end_date and end_date < start_date:
        results.append(
            finding(
                contract_id=contract_id,
                rule_id="DQ_END_BEFORE_START",
                category="data_quality",
                evidence={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
            )
        )

    if paid_value > contract_value:
        results.append(
            finding(
                contract_id=contract_id,
                rule_id="DQ_PAID_EXCEEDS_CONTRACT_VALUE",
                category="data_quality",
                evidence={
                    "contract_value": str(contract_value),
                    "paid_value": str(paid_value),
                },
            )
        )

    if end_date and state in ACTIVE_STATES and end_date < as_of:
        results.append(
            finding(
                contract_id=contract_id,
                rule_id="REVIEW_ACTIVE_AFTER_END_DATE",
                category="human_review",
                evidence={
                    "state": state,
                    "end_date": end_date.isoformat(),
                    "as_of": as_of.isoformat(),
                },
            )
        )
    elif (
        end_date
        and state in ACTIVE_STATES
        and as_of <= end_date <= as_of + timedelta(days=30)
    ):
        results.append(
            finding(
                contract_id=contract_id,
                rule_id="REVIEW_ENDING_WITHIN_30_DAYS",
                category="human_review",
                evidence={
                    "state": state,
                    "end_date": end_date.isoformat(),
                    "as_of": as_of.isoformat(),
                },
            )
        )

    contract_extension = parse_decimal(
        contract.get("dias_adicionados"),
        "dias_adicionados",
    )
    modification_extensions = [
        parse_decimal(modification.get("dias_extendidos"), "dias_extendidos")
        for modification in modifications
    ]
    positive_extensions = [
        extension
        for extension in [contract_extension, *modification_extensions]
        if extension > 0
    ]
    if positive_extensions:
        results.append(
            finding(
                contract_id=contract_id,
                rule_id="REVIEW_EXTENSION_RECORDED",
                category="human_review",
                evidence={
                    "contract_days_added": str(contract_extension),
                    "linked_modification_versions": len(modification_extensions),
                    "max_modification_days_extended": str(
                        max(modification_extensions, default=Decimal(0))
                    ),
                },
            )
        )

    return results


def conflict_findings(
    conflicts: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        finding(
            contract_id=str(conflict["id_contrato"]),
            rule_id="DQ_MODIFICATION_VERSION_CONFLICT",
            category="data_quality",
            evidence={
                "identificador_modificacion": str(
                    conflict["identificador_modificacion"]
                ),
                "numero_version": str(conflict["numero_version"]),
                "differing_fields": list(conflict["differing_fields"]),
                "representations": int(conflict["representations"]),
            },
        )
        for conflict in conflicts
    ]
