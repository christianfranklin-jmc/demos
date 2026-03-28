"""Tool: NL-to-SQL query pipeline with self-correction and caching.

Provides the Query Agent's core capabilities: intent classification,
schema-aware SQL generation, EXPLAIN validation with self-correction,
and semantic result caching.
"""

from __future__ import annotations

import hashlib
import logging
import time

from strands import tool

logger = logging.getLogger(__name__)

# In-memory cache (replaced by ElastiCache in production)
_query_cache: dict[str, dict] = {}


@tool
def classify_query_intent(
    question: str,
) -> dict:
    """Classify a natural language question by intent type.

    Routes questions to the appropriate handling path:
    - "sql": Requires database query (SELECT statement)
    - "metadata": Answerable from schema/catalog metadata alone
    - "visualization": Needs query + chart/graph output
    - "definition": Asks about a business term or metric definition

    Args:
        question: The natural language question from the user.
    """
    q = question.upper()

    # Visualization signals
    viz_keywords = [
        "CHART", "GRAPH", "PLOT", "TREND", "OVER TIME", "VISUALI",
        "BAR", "PIE", "LINE", "HISTOGRAM", "DISTRIBUTION",
    ]
    if any(kw in q for kw in viz_keywords):
        return {
            "intent": "visualization",
            "question": question,
            "requires_query": True,
            "requires_chart": True,
        }

    # Metadata signals
    meta_keywords = [
        "WHAT TABLES", "LIST TABLES", "WHAT COLUMNS", "DESCRIBE",
        "SCHEMA", "HOW MANY TABLES", "WHAT DATABASE", "SHOW ME THE STRUCTURE",
    ]
    if any(kw in q for kw in meta_keywords):
        return {
            "intent": "metadata",
            "question": question,
            "requires_query": False,
            "requires_chart": False,
        }

    # Definition signals
    def_keywords = [
        "WHAT IS", "WHAT DOES", "DEFINE", "MEANING OF", "DEFINITION",
        "WHAT'S THE DIFFERENCE BETWEEN",
    ]
    if any(kw in q for kw in def_keywords) and not any(
        kw in q for kw in ["HOW MANY", "TOP", "TOTAL", "SUM", "AVG", "COUNT"]
    ):
        return {
            "intent": "definition",
            "question": question,
            "requires_query": False,
            "requires_chart": False,
        }

    # Default: SQL query
    return {
        "intent": "sql",
        "question": question,
        "requires_query": True,
        "requires_chart": False,
    }


@tool
def check_query_cache(
    question: str,
    similarity_threshold: float = 0.92,
) -> dict:
    """Check the semantic cache for a previously answered similar question.

    Uses exact match on normalized question text. In production, this would
    use ElastiCache with vector similarity search.

    Args:
        question: The natural language question to check.
        similarity_threshold: Minimum similarity score for cache hit (0-1).
    """
    cache_key = _normalize_question(question)

    if cache_key in _query_cache:
        cached = _query_cache[cache_key]
        age_seconds = time.time() - cached.get("timestamp", 0)
        ttl_days = 7
        if age_seconds < ttl_days * 86400:
            return {
                "cache_hit": True,
                "question": question,
                "cached_sql": cached.get("sql", ""),
                "cached_result": cached.get("result", {}),
                "age_seconds": int(age_seconds),
            }

    return {
        "cache_hit": False,
        "question": question,
        "cache_size": len(_query_cache),
    }


@tool
def validate_and_execute_query(
    source_id: str,
    sql: str,
    max_rows: int = 100,
    max_retries: int = 3,
) -> dict:
    """Validate SQL with EXPLAIN, then execute. Self-corrects on error.

    Runs EXPLAIN first to catch syntax/semantic errors without hitting
    data. If EXPLAIN fails, attempts to fix the SQL up to max_retries times.
    On success, executes the query and returns results.

    Args:
        source_id: The source identifier from connect_to_database.
        sql: The SQL SELECT statement to validate and execute.
        max_rows: Maximum rows to return.
        max_retries: Maximum self-correction attempts on EXPLAIN failure.
    """
    import sys
    sys.path.insert(0, "/app/src")
    from platform_agent.drivers import get_driver

    driver = get_driver(source_id)
    attempts = []

    current_sql = sql
    for attempt in range(max_retries + 1):
        # Try EXPLAIN first
        try:
            driver.execute_query(f"EXPLAIN {current_sql}", max_rows=50)
            explain_ok = True
            explain_error = None
        except Exception as e:
            explain_ok = False
            explain_error = str(e)

        attempts.append({
            "attempt": attempt + 1,
            "sql": current_sql,
            "explain_ok": explain_ok,
            "error": explain_error,
        })

        if explain_ok:
            break

        if attempt < max_retries:
            # Try basic self-correction
            current_sql = _attempt_fix(current_sql, explain_error or "")
        else:
            return {
                "status": "failed",
                "message": (
                    f"SQL failed EXPLAIN after {max_retries + 1} attempts. "
                    f"Last error: {explain_error}"
                ),
                "attempts": attempts,
                "final_sql": current_sql,
            }

    # Execute the validated SQL
    try:
        result = driver.execute_query(current_sql, max_rows=max_rows)
        return {
            "status": "success",
            "sql": current_sql,
            "columns": result.get("columns", []),
            "rows": result.get("rows", []),
            "row_count": result.get("row_count", 0),
            "truncated": result.get("truncated", False),
            "attempts": len(attempts),
            "self_corrected": len(attempts) > 1,
        }
    except Exception as e:
        return {
            "status": "execution_error",
            "sql": current_sql,
            "error": str(e),
            "attempts": attempts,
        }


@tool
def cache_query_result(
    question: str,
    sql: str,
    result: dict,
) -> dict:
    """Store a query result in the semantic cache for future reuse.

    Args:
        question: The original natural language question.
        sql: The SQL that answered the question.
        result: The query result to cache (columns + rows).
    """
    cache_key = _normalize_question(question)
    _query_cache[cache_key] = {
        "sql": sql,
        "result": {
            "columns": result.get("columns", []),
            "rows": result.get("rows", [])[:20],  # Cache first 20 rows
            "row_count": result.get("row_count", 0),
        },
        "timestamp": time.time(),
    }

    return {
        "status": "cached",
        "cache_key": cache_key,
        "cache_size": len(_query_cache),
        "rows_cached": min(result.get("row_count", 0), 20),
    }


@tool
def get_table_schema_for_query(
    source_id: str,
    tables: list[str] | None = None,
) -> dict:
    """Get a compact schema representation optimized for SQL generation.

    Returns table names, column names with types, and join paths —
    the minimum context needed for NL-to-SQL translation.

    Args:
        source_id: The source identifier from connect_to_database.
        tables: Optional list of tables. If empty, returns all.
    """
    import sys
    sys.path.insert(0, "/app/src")
    from platform_agent.drivers import get_driver

    driver = get_driver(source_id)
    metadata = driver.scan_metadata()

    all_tables = metadata.get("tables", [])
    if tables:
        all_tables = [t for t in all_tables if t.get("table_name") in tables]

    compact: list[dict] = []
    join_paths: list[dict] = []

    for tbl in all_tables:
        tname = tbl.get("table_name", "")
        cols = [
            {"name": c.get("column_name", ""), "type": c.get("data_type", "")}
            for c in tbl.get("columns", [])
        ]
        compact.append({
            "table": tname,
            "columns": cols,
            "primary_key": tbl.get("primary_key", []),
            "row_count": tbl.get("row_count", 0),
        })

        for fk in tbl.get("foreign_keys", []):
            join_paths.append({
                "from_table": tname,
                "from_column": fk.get("source_column", ""),
                "to_table": fk.get("target_table", ""),
                "to_column": fk.get("target_column", ""),
            })

    return {
        "source_id": source_id,
        "table_count": len(compact),
        "tables": compact,
        "join_paths": join_paths,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_question(question: str) -> str:
    """Normalize a question for cache key matching."""
    normalized = question.lower().strip()
    normalized = " ".join(normalized.split())
    return hashlib.md5(normalized.encode()).hexdigest()


def _attempt_fix(sql: str, error: str) -> str:
    """Attempt basic SQL self-correction based on error message."""
    error_lower = error.lower()

    # Common fixes
    if "does not exist" in error_lower and '"' not in sql:
        # Try quoting identifiers
        return sql  # Would need actual identifier analysis

    if "ambiguous" in error_lower:
        # Can't fix without knowing which table — return as-is
        return sql

    if "syntax error" in error_lower:
        # Remove trailing semicolons that some engines don't like
        fixed = sql.rstrip().rstrip(";")
        if fixed != sql:
            return fixed

    # No fix found
    return sql
