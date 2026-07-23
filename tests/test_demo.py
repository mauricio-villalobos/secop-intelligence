from __future__ import annotations

from pathlib import Path

import duckdb

from secop_intelligence.demo import (
    DEMO_CONTRACT_COUNT,
    build_demo_database,
    ensure_demo_database,
    resolve_database,
)


def test_demo_database_is_deterministic_and_non_identifying(
    tmp_path: Path,
) -> None:
    database = tmp_path / "demo.duckdb"
    manifest = build_demo_database(database)

    assert manifest["result"] == "PASS"
    assert manifest["contract_count"] == DEMO_CONTRACT_COUNT
    assert manifest["finding_count"] == 30

    with duckdb.connect(str(database), read_only=True) as connection:
        contract_count, distinct_count = connection.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT contract_id)
            FROM contracts
            """
        ).fetchone()
        real_process_urls = connection.execute(
            "SELECT COUNT(*) FROM contracts WHERE process_url IS NOT NULL"
        ).fetchone()[0]
        invalid_entities = connection.execute(
            """
            SELECT COUNT(*)
            FROM contracts
            WHERE NOT starts_with(entity_name, 'Entidad demostrativa ')
            """
        ).fetchone()[0]
        inconsistent_active_dates = connection.execute(
            """
            SELECT COUNT(*)
            FROM attention_findings AS f
            JOIN contracts AS c USING (contract_id)
            WHERE f.rule_id = 'REVIEW_ACTIVE_AFTER_END_DATE'
              AND CAST(c.ends_at AS DATE) != TRY_CAST(
                  json_extract_string(f.evidence_json, '$.end_date') AS DATE
              )
            """
        ).fetchone()[0]
        conflicts_without_modifications = connection.execute(
            """
            SELECT COUNT(*)
            FROM attention_findings AS f
            LEFT JOIN modifications AS m USING (contract_id)
            WHERE f.rule_id = 'DQ_MODIFICATION_VERSION_CONFLICT'
            GROUP BY f.finding_id
            HAVING COUNT(m.modification_id) = 0
            """
        ).fetchall()

    assert contract_count == distinct_count == DEMO_CONTRACT_COUNT
    assert real_process_urls == 0
    assert invalid_entities == 0
    assert inconsistent_active_dates == 0
    assert conflicts_without_modifications == []


def test_ensure_demo_database_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "demo.duckdb"

    first = ensure_demo_database(database)
    first_mtime = first.stat().st_mtime_ns
    second = ensure_demo_database(database)

    assert second == first
    assert second.stat().st_mtime_ns == first_mtime


def test_demo_mode_can_be_explicit(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SECOP_DEMO_MODE", "1")

    database, is_demo = resolve_database()

    assert is_demo is True
    assert database.is_file()
