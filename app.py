from __future__ import annotations

from pathlib import Path

import streamlit as st

from secop_intelligence.analytics import (
    ALL,
    AnalyticsDatabaseError,
    filter_options,
    overview,
    present_queue,
    present_rule_counts,
    review_queue,
    rule_counts,
)

DATABASE = Path("data/warehouse/secop.duckdb")

st.set_page_config(
    page_title="SECOP Intelligence",
    page_icon="🔎",
    layout="wide",
)

st.title("SECOP Intelligence")
st.caption(
    "Deterministic decision support over privacy-minimized public data. "
    "Findings require human review and are not allegations."
)

try:
    metrics = overview(DATABASE)
    options = filter_options(DATABASE)
except AnalyticsDatabaseError as error:
    st.error(str(error))
    st.code("uv run secop-build-warehouse")
    st.stop()

columns = st.columns(5)
columns[0].metric("Contracts", metrics["contract_count"])
columns[1].metric("Findings", metrics["finding_count"])
columns[2].metric("Contracts flagged", metrics["contracts_with_findings"])
columns[3].metric("Human review", metrics["human_review_count"])
columns[4].metric("Data quality", metrics["data_quality_count"])

summary_tab, queue_tab, methodology_tab = st.tabs(
    ["Rule summary", "Review queue", "Methodology"]
)

with summary_tab:
    st.subheader("Transparent rule counts")
    counts = present_rule_counts(rule_counts(DATABASE))
    st.dataframe(
        counts,
        width="stretch",
        hide_index=True,
        column_config={
            "Findings": st.column_config.NumberColumn(format="%d"),
        },
    )

with queue_tab:
    filter_columns = st.columns(3)
    category = filter_columns[0].selectbox("Category", options["categories"])
    rule_id = filter_columns[1].selectbox("Rule", options["rules"])
    contract_state = filter_columns[2].selectbox(
        "Contract state",
        options["states"],
    )
    queue = present_queue(
        review_queue(
            DATABASE,
            category=category,
            rule_id=rule_id,
            contract_state=contract_state,
        )
    )
    st.caption(f"{len(queue)} evidence-bearing findings")
    st.dataframe(
        queue,
        width="stretch",
        hide_index=True,
        column_config={
            "Value (COP)": st.column_config.NumberColumn(format="localized"),
            "Evidence": st.column_config.TextColumn(width="large"),
        },
    )

with methodology_tab:
    st.markdown(
        """
        - Source records are requested from official SECOP II datasets.
        - Personal identifiers and banking fields are excluded by allowlist.
        - Conflicting modification versions are quarantined.
        - Every finding identifies its deterministic rule and evidence.
        - The interface opens DuckDB in read-only mode.
        - No composite risk score, fraud classification or automatic decision
          is produced.
        """
    )

st.caption(f"Ruleset 1.0 · Database: {DATABASE} · Filters default to {ALL}")
