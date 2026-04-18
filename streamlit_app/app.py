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
from platform_agent.drivers import create_driver

# ---------------------------------------------------------------------------
# Helper functions (must be defined before use in Streamlit's top-to-bottom execution)
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


# ---------------------------------------------------------------------------
# Page config + phData branding
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Talk To Your Data | phData", page_icon="📊", layout="wide")

# phData brand palette — dark-mode native
NAVY = "#1B2A4A"
BLUE = "#2563EB"
TEAL = "#0D9488"
ORANGE = "#F97316"
SURFACE_DARK = "#0F172A"
SURFACE_CARD = "#1E293B"
TEXT_PRIMARY = "#F1F5F9"
TEXT_SECONDARY = "#94A3B8"

st.markdown(f"""
<style>
    /* phData dark theme */
    .stApp {{
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }}
    header[data-testid="stHeader"] {{
        background-color: {SURFACE_DARK};
    }}
    /* Primary button */
    .stButton > button[kind="primary"] {{
        background-color: {BLUE};
        border-color: {BLUE};
        color: #FFFFFF;
    }}
    .stButton > button[kind="primary"]:hover {{
        background-color: #1D4ED8;
        border-color: #1D4ED8;
    }}
    /* Sidebar — dark surface, legible text */
    section[data-testid="stSidebar"] {{
        background-color: {SURFACE_DARK};
    }}
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {{
        color: {TEXT_PRIMARY};
    }}
    section[data-testid="stSidebar"] label {{
        color: {TEXT_PRIMARY} !important;
    }}
    section[data-testid="stSidebar"] .stTextInput input,
    section[data-testid="stSidebar"] .stNumberInput input,
    section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] {{
        color: {TEXT_PRIMARY};
        background-color: {SURFACE_CARD};
    }}
    /* Chat messages */
    .stChatMessage[data-testid="stChatMessage"] {{
        border-radius: 8px;
    }}
    /* Tab accent */
    .stTabs [data-baseweb="tab-highlight"] {{
        background-color: {BLUE};
    }}
    /* Title styling */
    .phdata-title {{
        color: {TEXT_PRIMARY};
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0;
        font-family: 'Inter', system-ui, sans-serif;
    }}
    .phdata-subtitle {{
        color: {TEAL};
        font-size: 1rem;
        margin-top: 0;
        font-family: 'Inter', system-ui, sans-serif;
    }}
    /* Backend mode badge */
    .backend-badge {{
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        font-family: 'Inter', system-ui, sans-serif;
        margin-left: 8px;
        vertical-align: middle;
    }}
    .badge-local {{
        background-color: {SURFACE_CARD};
        color: {TEAL};
        border: 1px solid {TEAL};
    }}
    .badge-agentcore {{
        background-color: {SURFACE_CARD};
        color: {ORANGE};
        border: 1px solid {ORANGE};
    }}
</style>
""", unsafe_allow_html=True)

# Detect AgentCore mode
_agentcore_url = os.environ.get("AGENTCORE_RUNTIME_URL") or os.environ.get(
    "AGENTCORE_ENDPOINT"
)
_is_agentcore = bool(_agentcore_url)
_badge_class = "badge-agentcore" if _is_agentcore else "badge-local"
_badge_label = "AgentCore" if _is_agentcore else "Local Agent"

st.markdown(
    f'<p class="phdata-title">Talk To Your Data'
    f'<span class="backend-badge {_badge_class}">{_badge_label}</span></p>',
    unsafe_allow_html=True,
)
st.markdown(
    '<p class="phdata-subtitle">Ask questions about your data in plain English. '
    'The agent discovers the schema on connect — no prior knowledge required.</p>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar — connection settings
# ---------------------------------------------------------------------------
with st.sidebar:
    if _is_agentcore:
        st.info(f"Backend: **AgentCore Runtime**\n\n`{_agentcore_url}`")
    else:
        st.caption("Backend: **Local Strands Agent** (direct Bedrock)")
    st.header("Database Connection")
    host = st.text_input("Host", value=os.environ.get("DB_HOST", ""))
    port = st.number_input("Port", value=int(os.environ.get("DB_PORT", "5432")), step=1)
    database = st.text_input("Database", value=os.environ.get("DB_NAME", ""))
    user = st.text_input("User", value=os.environ.get("DB_USER", ""))
    password = st.text_input("Password", type="password",
                             value=os.environ.get("DB_PASSWORD", ""))
    driver_type = st.selectbox("Database Type", ["postgresql", "redshift", "snowflake"],
        index=0)

    # Snowflake-specific fields
    if driver_type == "snowflake":
        sf_account = st.text_input("Account", value=os.environ.get("SF_ACCOUNT", ""))
        sf_warehouse = st.text_input("Warehouse", value=os.environ.get("SF_WAREHOUSE", ""))
        sf_role = st.text_input("Role", value=os.environ.get("SF_ROLE", ""))
        sf_authenticator = st.selectbox("Auth Method",
            ["externalbrowser", "password"], index=0)
        sf_schema = st.text_input("Schema", value=os.environ.get("SF_SCHEMA", "PUBLIC"))

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
    # Validate required fields based on driver type
    if driver_type == "snowflake":
        if not all([sf_account, database, user]):
            st.sidebar.error("Account, Database, and User are required for Snowflake.")
            connect_btn = False
    elif not all([host, database, user, password]):
        st.sidebar.error("All connection fields are required.")
        connect_btn = False

if connect_btn:
    with st.spinner("Connecting and discovering schema..."):
        try:
            source_id = f"{driver_type}_{database}"
            if driver_type == "snowflake":
                create_driver(
                    driver_type="snowflake",
                    source_id=source_id,
                    account=sf_account,
                    user=user,
                    password=password if sf_authenticator == "password" else "",
                    warehouse=sf_warehouse,
                    database=database,
                    schema=sf_schema,
                    role=sf_role,
                    authenticator=sf_authenticator,
                )
            else:
                create_driver(
                    driver_type=driver_type,
                    source_id=source_id,
                    host=host, port=int(port), database=database,
                    user=user, password=password,
                )

            agent = create_agent(profile_name=aws_profile)

            # Ask the agent to scan and learn the schema
            scan_result = agent(
                f"The database is connected with source_id='{source_id}'. "
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
            summary = "\n".join(lines[:20]) if lines else "Schema discovered."
            st.session_state.schema_summary = summary

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
# Empty state — shown before connection
# ---------------------------------------------------------------------------
if not st.session_state.connected and not st.session_state.messages:
    st.markdown(f"""
<div style="text-align: center; padding: 4rem 2rem;">
    <h3 style="color: {TEXT_PRIMARY}; font-family: Inter, system-ui, sans-serif;">
        Connect to get started
    </h3>
    <p style="color: {TEXT_SECONDARY}; max-width: 480px; margin: 0 auto;
              font-family: Inter, system-ui, sans-serif;">
        Enter your database credentials in the sidebar and click
        <strong style="color: {TEXT_PRIMARY};">Connect &amp; Discover Schema</strong>.
        The agent will scan your tables, columns, and relationships,
        then you can ask questions in plain English.
    </p>
    <p style="color: #64748B; font-size: 0.85rem; margin-top: 1.5rem;
              font-family: Inter, system-ui, sans-serif;">
        Supports PostgreSQL and Redshift. Read-only — your data is never modified.
    </p>
</div>
""", unsafe_allow_html=True)

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
        with st.chat_message("assistant"), st.spinner("Thinking..."):
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
