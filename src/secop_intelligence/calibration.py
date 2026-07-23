from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb


class CalibrationError(ValueError):
    """Raised when a calibration profile cannot be produced."""


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def build_calibration_profile(
    database: Path,
    *,
    top_entities: int = 10,
) -> dict[str, Any]:
    if not database.is_file():
        raise CalibrationError(f"database not found: {database}")
    if not 1 <= top_entities <= 100:
        raise ValueError("top_entities must be between 1 and 100")

    with duckdb.connect(str(database), read_only=True) as connection:
        contract_count = int(
            connection.execute("SELECT COUNT(*) FROM contracts").fetchone()[0]
        )
        finding_count = int(
            connection.execute("SELECT COUNT(*) FROM attention_findings").fetchone()[0]
        )
        flagged_count = int(
            connection.execute(
                "SELECT COUNT(DISTINCT contract_id) FROM attention_findings"
            ).fetchone()[0]
        )

        rule_rows = connection.execute(
            """
            SELECT
                f.category,
                f.rule_id,
                COUNT(*) AS finding_count,
                COUNT(DISTINCT f.contract_id) AS contract_count
            FROM attention_findings AS f
            GROUP BY f.category, f.rule_id
            ORDER BY finding_count DESC, f.rule_id
            """
        ).fetchall()

        state_rows = connection.execute(
            """
            SELECT
                f.rule_id,
                COALESCE(c.contract_state, '<missing>') AS contract_state,
                COUNT(*) AS finding_count,
                COUNT(DISTINCT f.contract_id) AS contract_count
            FROM attention_findings AS f
            JOIN contracts AS c USING (contract_id)
            GROUP BY f.rule_id, contract_state
            ORDER BY f.rule_id, finding_count DESC, contract_state
            """
        ).fetchall()

        entity_rows = connection.execute(
            """
            WITH ranked AS (
                SELECT
                    f.rule_id,
                    COALESCE(c.entity_name, '<missing>') AS entity_name,
                    COUNT(*) AS finding_count,
                    COUNT(DISTINCT f.contract_id) AS contract_count,
                    ROW_NUMBER() OVER (
                        PARTITION BY f.rule_id
                        ORDER BY
                            COUNT(*) DESC,
                            COALESCE(c.entity_name, '<missing>')
                    ) AS entity_rank
                FROM attention_findings AS f
                JOIN contracts AS c USING (contract_id)
                GROUP BY f.rule_id, entity_name
            )
            SELECT
                rule_id,
                entity_name,
                finding_count,
                contract_count
            FROM ranked
            WHERE entity_rank <= ?
            ORDER BY rule_id, finding_count DESC, entity_name
            """,
            [top_entities],
        ).fetchall()
        overdue_rows = connection.execute(
            """
            WITH extension_contracts AS (
                SELECT DISTINCT contract_id
                FROM attention_findings
                WHERE rule_id = 'REVIEW_EXTENSION_RECORDED'
            ),
            target AS (
                SELECT
                    f.contract_id,
                    c.contract_state,
                    c.ends_at,
                    TRY_CAST(
                        json_extract_string(f.evidence_json, '$.as_of') AS DATE
                    ) AS as_of,
                    extension.contract_id IS NOT NULL AS has_extension_finding
                FROM attention_findings AS f
                JOIN contracts AS c USING (contract_id)
                LEFT JOIN extension_contracts AS extension USING (contract_id)
                WHERE f.rule_id = 'REVIEW_ACTIVE_AFTER_END_DATE'
            ),
            bucketed AS (
                SELECT
                    COALESCE(contract_state, '<missing>') AS contract_state,
                    CASE
                        WHEN ends_at IS NULL OR as_of IS NULL THEN 'unknown'
                        WHEN date_diff('day', CAST(ends_at AS DATE), as_of) <= 30
                            THEN '01-30 days'
                        WHEN date_diff('day', CAST(ends_at AS DATE), as_of) <= 90
                            THEN '31-90 days'
                        WHEN date_diff('day', CAST(ends_at AS DATE), as_of) <= 180
                            THEN '91-180 days'
                        WHEN date_diff('day', CAST(ends_at AS DATE), as_of) <= 365
                            THEN '181-365 days'
                        ELSE '366+ days'
                    END AS overdue_bucket,
                    has_extension_finding
                FROM target
            )
            SELECT
                contract_state,
                overdue_bucket,
                has_extension_finding,
                COUNT(*) AS contract_count
            FROM bucketed
            GROUP BY contract_state, overdue_bucket, has_extension_finding
            ORDER BY contract_state, overdue_bucket, has_extension_finding
            """
        ).fetchall()

    rules = [
        {
            "category": str(category),
            "rule_id": str(rule_id),
            "finding_count": int(findings),
            "contract_count": int(contracts),
            "contract_prevalence": _ratio(int(contracts), contract_count),
            "share_of_findings": _ratio(int(findings), finding_count),
        }
        for category, rule_id, findings, contracts in rule_rows
    ]
    by_state = [
        {
            "rule_id": str(rule_id),
            "contract_state": str(state),
            "finding_count": int(findings),
            "contract_count": int(contracts),
        }
        for rule_id, state, findings, contracts in state_rows
    ]
    by_entity = [
        {
            "rule_id": str(rule_id),
            "entity_name": str(entity),
            "finding_count": int(findings),
            "contract_count": int(contracts),
        }
        for rule_id, entity, findings, contracts in entity_rows
    ]
    active_after_end_profile = [
        {
            "contract_state": str(state),
            "overdue_bucket": str(bucket),
            "has_extension_finding": bool(has_extension),
            "contract_count": int(contracts),
        }
        for state, bucket, has_extension, contracts in overdue_rows
    ]

    rule_totals = {str(item["rule_id"]): int(item["finding_count"]) for item in rules}
    state_totals: dict[str, int] = {}
    for item in by_state:
        rule_id = str(item["rule_id"])
        state_totals[rule_id] = state_totals.get(rule_id, 0) + int(
            item["finding_count"]
        )
    if state_totals != rule_totals:
        raise CalibrationError("state profile does not reconcile with rule totals")

    expected_active = rule_totals.get("REVIEW_ACTIVE_AFTER_END_DATE", 0)
    profiled_active = sum(
        int(item["contract_count"]) for item in active_after_end_profile
    )
    if profiled_active != expected_active:
        raise CalibrationError(
            "active-after-end profile does not reconcile with rule total"
        )

    return {
        "schema_version": 1,
        "result": "PASS",
        "contract_count": contract_count,
        "finding_count": finding_count,
        "flagged_contract_count": flagged_count,
        "flagged_contract_prevalence": _ratio(flagged_count, contract_count),
        "rules": rules,
        "by_state": by_state,
        "top_entities_per_rule": by_entity,
        "active_after_end_profile": active_after_end_profile,
        "reconciliation": {
            "rule_findings_equal_state_findings": True,
            "active_after_end_profile_total": profiled_active,
            "active_after_end_rule_total": expected_active,
        },
        "interpretation_guardrail": (
            "Descriptive calibration only; no score, allegation, or automated decision."
        ),
    }
