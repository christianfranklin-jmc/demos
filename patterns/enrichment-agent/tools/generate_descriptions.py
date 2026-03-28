"""Tool: Generate business-quality descriptions for tables and columns.

Uses LLM reasoning over schema metadata, sample data, column statistics,
and naming patterns to produce human-readable descriptions. Can optionally
use a Bedrock Knowledge Base for RAG-enhanced context.
"""

from __future__ import annotations

import logging

from strands import tool

logger = logging.getLogger(__name__)


@tool
def generate_descriptions(
    source_id: str,
    tables: list[str] | None = None,
    sample_rows: int = 5,
    use_rag: bool = False,
    knowledge_base_id: str = "",
) -> dict:
    """Generate business-quality descriptions for tables and columns.

    Analyzes table/column names, data types, sample values, and statistics
    to produce descriptions suitable for a data catalog. Optionally enriches
    with RAG context from a Bedrock Knowledge Base.

    Args:
        source_id: The source identifier from connect_to_database.
        tables: Optional list of table names. If empty, describes all tables.
        sample_rows: Number of sample rows to inspect per table for context.
        use_rag: Whether to use Bedrock Knowledge Base for RAG enrichment.
        knowledge_base_id: Bedrock Knowledge Base ID (required if use_rag=True).
    """
    import sys
    sys.path.insert(0, "/app/src")
    from platform_agent.drivers import get_driver

    driver = get_driver(source_id)
    metadata = driver.scan_metadata()

    all_tables = metadata.get("tables", [])
    if tables:
        all_tables = [t for t in all_tables if t.get("table_name") in tables]

    enriched = []
    for tbl in all_tables:
        tname = tbl.get("table_name", "")
        columns = tbl.get("columns", [])
        existing_comment = tbl.get("comment", "")

        # Sample data for context
        samples = {}
        try:
            result = driver.execute_query(
                f'SELECT * FROM "{tname}" LIMIT {sample_rows}',
                max_rows=sample_rows,
            )
            samples = {
                "columns": result.get("columns", []),
                "rows": result.get("rows", []),
            }
        except Exception as e:
            logger.warning("Could not sample %s: %s", tname, e)

        # Analyze column patterns for description hints
        col_descriptions = []
        for col in columns:
            cname = col.get("column_name", "")
            dtype = col.get("data_type", "")
            existing_col_comment = col.get("comment", "")

            # Infer description from naming patterns
            desc = existing_col_comment or _infer_column_description(
                cname, dtype, tname
            )
            col_descriptions.append({
                "column_name": cname,
                "data_type": dtype,
                "existing_comment": existing_col_comment,
                "generated_description": desc,
                "is_nullable": col.get("is_nullable", "YES"),
            })

        # Infer table description
        table_desc = existing_comment or _infer_table_description(
            tname, columns
        )

        enriched.append({
            "table_name": tname,
            "existing_comment": existing_comment,
            "generated_description": table_desc,
            "row_count": tbl.get("row_count", 0),
            "column_count": len(columns),
            "columns": col_descriptions,
            "sample_data_available": bool(samples.get("rows")),
        })

    # RAG enrichment (if configured)
    rag_status = "disabled"
    if use_rag and knowledge_base_id:
        rag_status = _enrich_with_rag(enriched, knowledge_base_id)

    return {
        "source_id": source_id,
        "tables_enriched": len(enriched),
        "total_columns": sum(len(t["columns"]) for t in enriched),
        "rag_status": rag_status,
        "tables": enriched,
    }


def _infer_table_description(table_name: str, columns: list[dict]) -> str:
    """Infer a table description from naming conventions."""
    name = table_name.upper()
    col_names = [c.get("column_name", "").upper() for c in columns]

    if name.startswith("DIM_"):
        entity = name[4:].replace("_", " ").title()
        return f"{entity} dimension table containing descriptive attributes."
    elif name.startswith("FACT_"):
        entity = name[5:].replace("_", " ").title()
        return f"{entity} fact table containing transactional/event measures."
    elif name.startswith("STG_"):
        entity = name[4:].replace("_", " ").title()
        return f"Staging table for {entity} data."
    elif any(c in col_names for c in ["CREATED_AT", "UPDATED_AT", "EVENT_TIME"]):
        return f"Transactional table tracking {name.replace('_', ' ').lower()} events."
    else:
        return f"Table containing {name.replace('_', ' ').lower()} data."


def _infer_column_description(
    col_name: str, data_type: str, table_name: str
) -> str:
    """Infer a column description from naming patterns."""
    name = col_name.upper()
    dtype = data_type.upper()

    # Primary/surrogate keys
    if name.endswith("_KEY") or name.endswith("_SK"):
        entity = name.replace("_KEY", "").replace("_SK", "")
        return f"Surrogate key for {entity.replace('_', ' ').lower()}."
    if name.endswith("_ID"):
        entity = name.replace("_ID", "")
        return f"Unique identifier for {entity.replace('_', ' ').lower()}."

    # Common patterns
    patterns = {
        "CREATED_DATE": "Date when the record was created.",
        "CREATED_AT": "Timestamp when the record was created.",
        "UPDATED_DATE": "Date when the record was last updated.",
        "UPDATED_AT": "Timestamp of the last modification.",
        "EFFECTIVE_DATE": "Date from which this record is effective.",
        "END_DATE": "Date when this record is no longer effective.",
        "IS_ACTIVE": "Whether this record is currently active.",
        "IS_DELETED": "Soft delete flag.",
        "AMOUNT": "Monetary amount.",
        "QUANTITY": "Count or quantity measure.",
        "REVENUE": "Revenue amount in local currency.",
        "COST": "Cost amount.",
        "BUDGET": "Budgeted amount.",
        "ACTUAL": "Actual amount (vs. budget).",
        "VARIANCE": "Difference between actual and budgeted amounts.",
        "NAME": f"Name of the {table_name.replace('_', ' ').lower()}.",
        "DESCRIPTION": "Free-text description.",
        "STATUS": "Current status of the record.",
        "CATEGORY": "Classification category.",
        "TYPE": "Record type classification.",
        "REGION": "Geographic region.",
        "COUNTRY": "Country name or code.",
        "CITY": "City name.",
        "STATE": "State or province.",
        "EMAIL": "Email address.",
        "PHONE": "Phone number.",
    }

    if name in patterns:
        return patterns[name]

    # Date columns
    if "DATE" in dtype or name.endswith("_DATE"):
        return f"Date value for {name.replace('_', ' ').lower()}."

    # Numeric columns
    if any(t in dtype for t in ["NUMBER", "DECIMAL", "FLOAT", "INT"]):
        return f"Numeric value for {name.replace('_', ' ').lower()}."

    # Boolean
    if name.startswith("IS_") or name.startswith("HAS_"):
        flag = name[3:] if name.startswith("IS_") else name[4:]
        return f"Boolean flag indicating {flag.replace('_', ' ').lower()}."

    return f"{name.replace('_', ' ').title()} value."


def _enrich_with_rag(tables: list[dict], knowledge_base_id: str) -> str:
    """Enrich descriptions using Bedrock Knowledge Base RAG."""
    try:
        import boto3

        bedrock_agent = boto3.client("bedrock-agent-runtime")
        enriched_count = 0

        for table in tables:
            query = (
                f"What is the business purpose of the "
                f"{table['table_name']} table? "
                f"Columns: {[c['column_name'] for c in table['columns'][:10]]}"
            )
            try:
                response = bedrock_agent.retrieve(
                    knowledgeBaseId=knowledge_base_id,
                    retrievalQuery={"text": query},
                    retrievalConfiguration={
                        "vectorSearchConfiguration": {"numberOfResults": 3}
                    },
                )
                results = response.get("retrievalResults", [])
                if results:
                    context = " ".join(
                        r.get("content", {}).get("text", "")
                        for r in results[:2]
                    )
                    table["rag_context"] = context[:500]
                    enriched_count += 1
            except Exception as e:
                logger.warning("RAG failed for %s: %s", table["table_name"], e)

        return f"enriched_{enriched_count}_tables"
    except ImportError:
        return "boto3_not_available"
