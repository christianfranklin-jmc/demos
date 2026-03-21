"""Talk To Your Data — Streamlit conversational analytics app.

The agent discovers the schema dynamically on connect (scan_metadata),
then answers questions using run_query. No prior knowledge of the
database structure is assumed.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import streamlit as st

# Add project root to path so we can import platform_agent
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from platform_agent.agent import create_agent
from platform_agent.tools._toolkit_client import connect

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Talk To Your Data", page_icon="📊", layout="wide")
st.title("Talk To Your Data")
st.caption("Ask questions about your data in plain English. "
           "The agent discovers the schema on connect — no prior knowledge required.")

# ---------------------------------------------------------------------------
# Sidebar — connection settings
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Database Connection")
    host = st.text_input("Host", value=os.environ.get("DB_HOST", ""))
    port = st.number_input("Port", value=int(os.environ.get("DB_PORT", "5432")), step=1)
    database = st.text_input("Database", value=os.environ.get("DB_NAME", ""))
    user = st.text_input("User", value=os.environ.get("DB_USER", ""))
    password = st.text_input("Password", type="password",
                             value=os.environ.get("DB_PASSWORD", ""))
    aws_profile = st.text_input("AWS Profile", value=os.environ.get(
        "AWS_PROFILE", "AdministratorAccess-637119802057"))

    connect_btn = st.button("Connect & Discover Schema", type="primary")

    if st.session_state.get("connected"):
        st.success(f"Connected to **{st.session_state.get('db_name', '')}**")
        if st.session_state.get("schema_summary"):
            st.markdown("**Discovered tables:**")
            st.text(st.session_state["schema_summary"])

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent" not in st.session_state:
    st.session_state.agent = None
if "connected" not in st.session_state:
    st.session_state.connected = False
if "source_id" not in st.session_state:
    st.session_state.source_id = None
if "schema_context" not in st.session_state:
    st.session_state.schema_context = ""

# ---------------------------------------------------------------------------
# Connection + schema discovery handler
# ---------------------------------------------------------------------------
if connect_btn:
    if not all([host, database, user, password]):
        st.sidebar.error("All connection fields are required.")
    else:
        with st.spinner("Connecting and discovering schema..."):
            try:
                source_id = f"rds_postgresql_{database}"
                connect(
                    host=host, port=int(port), database=database,
                    user=user, password=password, source_id=source_id,
                )
                agent = create_agent(profile_name=aws_profile)

                # Ask the agent to scan and learn the schema
                scan_result = agent(
                    f"The database is already connected with source_id='{source_id}'. "
                    f"Use scan_metadata to discover all tables, columns, primary keys, "
                    f"and foreign keys. Then provide a brief summary of what you found — "
                    f"list each table with its row count and key columns."
                )
                schema_text = _extract_text(scan_result)

                st.session_state.agent = agent
                st.session_state.connected = True
                st.session_state.source_id = source_id
                st.session_state.db_name = database
                st.session_state.schema_context = schema_text

                # Build sidebar summary
                lines = []
                for line in schema_text.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("- ") or stripped.startswith("* "):
                        lines.append(stripped)
                st.session_state.schema_summary = "\n".join(lines[:20]) if lines else "Schema discovered."

                # Add discovery as first assistant message
                st.session_state.messages = [{
                    "role": "assistant",
                    "content": f"**Schema discovered.** Here's what I found:\n\n{schema_text}",
                }]
                st.rerun()

            except Exception as e:
                st.sidebar.error(f"Connection failed: {e}")

# ---------------------------------------------------------------------------
# Chat display
# ---------------------------------------------------------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "dataframe" in msg:
            st.dataframe(msg["dataframe"], use_container_width=True)
        if "chart_data" in msg:
            _render_chart(msg["chart_data"])

# ---------------------------------------------------------------------------
# Chat input
# ---------------------------------------------------------------------------
if prompt := st.chat_input("Ask a question about your data..."):
    if not st.session_state.connected:
        st.error("Please connect to a database first using the sidebar.")
    else:
        # Show user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get agent response — the agent already has schema context from the
        # scan_metadata call during connection. It uses run_query to answer.
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    agent = st.session_state.agent
                    source_id = st.session_state.source_id
                    full_prompt = (
                        f"The database is connected with source_id='{source_id}'. "
                        f"Use run_query to answer this question with actual data. "
                        f"If the question is ambiguous, use scan_metadata or run_query "
                        f"to explore the schema first. Question: {prompt}"
                    )
                    result = agent(full_prompt)
                    response_text = _extract_text(result)

                    st.markdown(response_text)

                    # Try to extract query results for display
                    df = _extract_query_results(result)
                    msg_data = {"role": "assistant", "content": response_text}
                    if df is not None and not df.empty:
                        st.dataframe(df, use_container_width=True)
                        msg_data["dataframe"] = df
                        # Auto-chart if small enough
                        chart = _auto_chart(df)
                        if chart:
                            msg_data["chart_data"] = chart

                    st.session_state.messages.append(msg_data)

                except Exception as e:
                    error_msg = f"Error: {e}"
                    st.error(error_msg)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": error_msg}
                    )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _extract_text(result) -> str:
    """Extract text content from agent response."""
    if hasattr(result, "message"):
        msg = result.message
        if hasattr(msg, "content") and isinstance(msg.content, list):
            texts = [block.get("text", "") for block in msg.content
                     if isinstance(block, dict) and "text" in block]
            return "\n".join(texts) if texts else str(result)
    return str(result)


def _extract_query_results(result) -> pd.DataFrame | None:
    """Extract the last query result from agent tool use."""
    if not hasattr(result, "message"):
        return None

    msg = result.message
    if not hasattr(msg, "content") or not isinstance(msg.content, list):
        return None

    # Walk through content blocks looking for tool results with rows
    for block in reversed(msg.content):
        if isinstance(block, dict) and block.get("type") == "tool_result":
            content = block.get("content", "")
            if isinstance(content, str) and '"rows"' in content:
                try:
                    import json
                    data = json.loads(content)
                    if "rows" in data and data["rows"]:
                        return pd.DataFrame(data["rows"])
                except (json.JSONDecodeError, ValueError):
                    pass
    return None


def _auto_chart(df: pd.DataFrame) -> dict | None:
    """Determine if data is suitable for auto-charting."""
    if df is None or df.empty or len(df) > 50 or len(df.columns) < 2:
        return None

    # Find numeric and non-numeric columns
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    cat_cols = [c for c in df.columns if c not in numeric_cols]

    if numeric_cols and cat_cols:
        return {"x": cat_cols[0], "y": numeric_cols[0], "df": df}
    return None


def _render_chart(chart_data: dict) -> None:
    """Render a bar chart from chart data."""
    df = chart_data["df"]
    x, y = chart_data["x"], chart_data["y"]
    st.bar_chart(df.set_index(x)[y])
