from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

ALL = "All"

RULE_LABELS = {
    "DQ_MODIFICATION_VERSION_CONFLICT": "Conflicting modification version",
    "REVIEW_ACTIVE_AFTER_END_DATE": "Active after contract end date",
    "REVIEW_ENDING_WITHIN_30_DAYS": "Ending within 30 days",
    "REVIEW_EXTENSION_RECORDED": "Extension recorded",
}

CATEGORY_LABELS = {
    "data_quality": "Data quality",
    "human_review": "Human review",
}


class AnalyticsDatabaseError(ValueError):
    """Raised when the accepted analytical database is unavailable."""


def _connect(database: Path) -> duckdb.DuckDBPyConnection:
    if not database.is_file():
        raise AnalyticsDatabaseError(f"database not found: {database}")
    return duckdb.connect(str(database), read_only=True)


def _rows(
    connection: duckdb.DuckDBPyConnection,
    query: str,
    parameters: list[Any] | None = None,
) -> list[dict[str, Any]]:
    result = connection.execute(query, parameters or [])
    columns = [item[0] for item in result.description]
    return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]


def overview(database: Path) -> dict[str, int]:
    with _connect(database) as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS contract_count,
                COALESCE(SUM(finding_count), 0) AS finding_count,
                COALESCE(SUM(data_quality_count), 0) AS data_quality_count,
                COALESCE(SUM(human_review_count), 0) AS human_review_count,
                COUNT(*) FILTER (
                    WHERE finding_count > 0
                ) AS contracts_with_findings
            FROM v_contract_attention_summary
            """
        ).fetchone()
    if row is None:
        raise AnalyticsDatabaseError("overview query returned no row")
    return {
        "contract_count": int(row[0]),
        "finding_count": int(row[1]),
        "data_quality_count": int(row[2]),
        "human_review_count": int(row[3]),
        "contracts_with_findings": int(row[4]),
    }


def filter_options(database: Path) -> dict[str, list[str]]:
    with _connect(database) as connection:
        categories = [
            str(row[0])
            for row in connection.execute(
                "SELECT DISTINCT category FROM attention_findings ORDER BY category"
            ).fetchall()
        ]
        rules = [
            str(row[0])
            for row in connection.execute(
                "SELECT DISTINCT rule_id FROM attention_findings ORDER BY rule_id"
            ).fetchall()
        ]
        states = [
            str(row[0])
            for row in connection.execute(
                "SELECT DISTINCT contract_state FROM contracts "
                "WHERE contract_state IS NOT NULL ORDER BY contract_state"
            ).fetchall()
        ]
    return {
        "categories": [ALL, *categories],
        "rules": [ALL, *rules],
        "states": [ALL, *states],
    }


def rule_counts(database: Path) -> list[dict[str, Any]]:
    with _connect(database) as connection:
        return _rows(
            connection,
            """
            SELECT category, rule_id, finding_count
            FROM v_rule_counts
            ORDER BY finding_count DESC, category, rule_id
            """,
        )


def review_queue(
    database: Path,
    *,
    category: str = ALL,
    rule_id: str = ALL,
    contract_state: str = ALL,
    limit: int = 200,
) -> list[dict[str, Any]]:
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")

    clauses: list[str] = []
    parameters: list[Any] = []
    for column, value in (
        ("f.category", category),
        ("f.rule_id", rule_id),
        ("c.contract_state", contract_state),
    ):
        if value != ALL:
            clauses.append(f"{column} = ?")
            parameters.append(value)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    parameters.append(limit)

    with _connect(database) as connection:
        return _rows(
            connection,
            f"""
            SELECT
                f.finding_id,
                f.contract_id,
                c.entity_name,
                c.department,
                c.contract_state,
                c.contract_value,
                f.category,
                f.rule_id,
                f.ruleset_version,
                CAST(f.evidence_json AS VARCHAR) AS evidence
            FROM attention_findings AS f
            JOIN contracts AS c USING (contract_id)
            {where}
            ORDER BY
                CASE f.category WHEN 'data_quality' THEN 0 ELSE 1 END,
                f.rule_id,
                f.contract_id,
                f.finding_id
            LIMIT ?
            """,
            parameters,
        )


def present_rule_counts(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "Category": CATEGORY_LABELS.get(
                str(item["category"]),
                str(item["category"]),
            ),
            "Rule": RULE_LABELS.get(str(item["rule_id"]), str(item["rule_id"])),
            "Rule ID": str(item["rule_id"]),
            "Findings": int(item["finding_count"]),
        }
        for item in records
    ]


def present_queue(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "Contract ID": str(item["contract_id"]),
            "Entity": item["entity_name"],
            "State": item["contract_state"],
            "Value (COP)": item["contract_value"],
            "Category": CATEGORY_LABELS.get(
                str(item["category"]),
                str(item["category"]),
            ),
            "Rule": RULE_LABELS.get(str(item["rule_id"]), str(item["rule_id"])),
            "Rule ID": str(item["rule_id"]),
            "Evidence": item["evidence"],
        }
        for item in records
    ]
