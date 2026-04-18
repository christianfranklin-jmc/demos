"""Tool: Build a knowledge graph from schema metadata and dbt lineage.

Extracts entities (tables, columns, metrics) and relationships (FKs,
lineage edges, business rules) to produce RDF triples loadable into
Amazon Neptune or any graph database.
"""

from __future__ import annotations

import json
import logging

from strands import tool

logger = logging.getLogger(__name__)


@tool
def extract_entities_and_relationships(
    source_id: str,
    tables: list[str] | None = None,
    include_columns: bool = True,
) -> dict:
    """Extract entities and relationships from database metadata for graph construction.

    Produces nodes (tables, columns) and edges (foreign keys, primary key
    ownership, same-name joins) from the connected database's schema.

    Args:
        source_id: The source identifier from connect_to_database.
        tables: Optional list of table names. If empty, extracts all.
        include_columns: Whether to include column-level nodes and edges.
    """
    import sys
    sys.path.insert(0, "/app/src")
    from platform_agent.drivers import get_driver

    driver = get_driver(source_id)
    metadata = driver.scan_metadata()

    all_tables = metadata.get("tables", [])
    if tables:
        all_tables = [t for t in all_tables if t.get("table_name") in tables]

    nodes: list[dict] = []
    edges: list[dict] = []
    database = metadata.get("database", "")
    schema = metadata.get("schema", "")

    for tbl in all_tables:
        tname = tbl.get("table_name", "")
        row_count = tbl.get("row_count", 0) or 0
        comment = tbl.get("comment", "")

        # Classify table type
        upper = tname.upper()
        if upper.startswith("DIM_"):
            table_type = "dimension"
        elif upper.startswith("FACT_"):
            table_type = "fact"
        elif upper.startswith("STG_"):
            table_type = "staging"
        else:
            table_type = "table"

        # Table node
        table_uri = f"{database}.{schema}.{tname}"
        nodes.append({
            "uri": table_uri,
            "type": "Table",
            "label": tname,
            "properties": {
                "database": database,
                "schema": schema,
                "table_type": table_type,
                "row_count": row_count,
                "comment": comment,
            },
        })

        if include_columns:
            for col in tbl.get("columns", []):
                cname = col.get("column_name", "")
                col_uri = f"{table_uri}.{cname}"
                nodes.append({
                    "uri": col_uri,
                    "type": "Column",
                    "label": cname,
                    "properties": {
                        "data_type": col.get("data_type", ""),
                        "is_nullable": col.get("is_nullable", "YES"),
                        "comment": col.get("comment", ""),
                    },
                })
                # Column belongs to table
                edges.append({
                    "source": col_uri,
                    "target": table_uri,
                    "relationship": "BELONGS_TO",
                })

            # Primary key edges
            for pk_col in tbl.get("primary_key", []):
                edges.append({
                    "source": f"{table_uri}.{pk_col}",
                    "target": table_uri,
                    "relationship": "IS_PRIMARY_KEY_OF",
                })

        # Foreign key edges
        for fk in tbl.get("foreign_keys", []):
            src_col = fk.get("source_column", "")
            tgt_table = fk.get("target_table", "")
            tgt_col = fk.get("target_column", "")
            src_uri = f"{table_uri}.{src_col}"
            tgt_uri = f"{database}.{schema}.{tgt_table}.{tgt_col}"
            edges.append({
                "source": src_uri,
                "target": tgt_uri,
                "relationship": "REFERENCES",
            })
            # Table-level relationship
            edges.append({
                "source": table_uri,
                "target": f"{database}.{schema}.{tgt_table}",
                "relationship": "JOINS_TO",
            })

    # Detect implicit joins (same column name across tables)
    col_tables: dict[str, list[str]] = {}
    for tbl in all_tables:
        tname = tbl.get("table_name", "")
        for col in tbl.get("columns", []):
            cname = col.get("column_name", "").upper()
            if cname.endswith("_KEY") or cname.endswith("_ID"):
                col_tables.setdefault(cname, []).append(tname)

    for col_name, tbl_list in col_tables.items():
        if len(tbl_list) > 1:
            for i in range(len(tbl_list)):
                for j in range(i + 1, len(tbl_list)):
                    edges.append({
                        "source": f"{database}.{schema}.{tbl_list[i]}",
                        "target": f"{database}.{schema}.{tbl_list[j]}",
                        "relationship": "IMPLICIT_JOIN",
                        "properties": {"join_column": col_name},
                    })

    return {
        "source_id": source_id,
        "database": database,
        "schema": schema,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "table_nodes": sum(1 for n in nodes if n["type"] == "Table"),
        "column_nodes": sum(1 for n in nodes if n["type"] == "Column"),
        "nodes": nodes,
        "edges": edges,
    }


@tool
def generate_rdf_triples(
    graph_data: dict,
    output_format: str = "ntriples",
) -> dict:
    """Convert extracted entities and relationships to RDF triples.

    Produces triples in N-Triples or JSON-LD format suitable for
    bulk loading into Amazon Neptune.

    Args:
        graph_data: Output from extract_entities_and_relationships.
        output_format: "ntriples" or "jsonld".
    """
    base_uri = "https://platform-agent.phdata.io/graph"
    triples: list[str] = []

    # Node triples
    for node in graph_data.get("nodes", []):
        subject = f"<{base_uri}/{node['uri']}>"
        triples.append(
            f'{subject} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> '
            f'"{ node["type"] }" .'
        )
        triples.append(
            f'{subject} <http://www.w3.org/2000/01/rdf-schema#label> '
            f'"{node["label"]}" .'
        )
        for prop_key, prop_val in node.get("properties", {}).items():
            if prop_val:
                escaped = str(prop_val).replace('"', '\\"')
                triples.append(
                    f'{subject} <{base_uri}/property/{prop_key}> '
                    f'"{escaped}" .'
                )

    # Edge triples
    for edge in graph_data.get("edges", []):
        subject = f"<{base_uri}/{edge['source']}>"
        obj = f"<{base_uri}/{edge['target']}>"
        predicate = f"<{base_uri}/relationship/{edge['relationship']}>"
        triples.append(f"{subject} {predicate} {obj} .")

    if output_format == "jsonld":
        # Convert to JSON-LD structure
        jsonld = {
            "@context": {
                "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                "pa": f"{base_uri}/",
            },
            "@graph": [],
        }
        for node in graph_data.get("nodes", []):
            entry = {
                "@id": f"pa:{node['uri']}",
                "@type": node["type"],
                "rdfs:label": node["label"],
            }
            for k, v in node.get("properties", {}).items():
                if v:
                    entry[f"pa:property/{k}"] = str(v)
            jsonld["@graph"].append(entry)

        return {
            "format": "jsonld",
            "triple_count": len(triples),
            "content": json.dumps(jsonld, indent=2),
        }

    return {
        "format": "ntriples",
        "triple_count": len(triples),
        "content": "\n".join(triples),
    }


@tool
def load_to_neptune(
    triples_data: dict,
    neptune_endpoint: str = "",
    s3_staging_bucket: str = "",
) -> dict:
    """Load RDF triples into Amazon Neptune via S3 bulk load.

    Writes triples to S3, then triggers Neptune's bulk loader.
    Requires Neptune endpoint and S3 staging bucket.

    Args:
        triples_data: Output from generate_rdf_triples.
        neptune_endpoint: Neptune cluster endpoint
            (e.g., neptune-cluster.us-east-1.neptune.amazonaws.com).
        s3_staging_bucket: S3 bucket for staging triple files.
    """
    import os

    neptune_endpoint = neptune_endpoint or os.environ.get("NEPTUNE_ENDPOINT", "")
    s3_staging_bucket = s3_staging_bucket or os.environ.get("NEPTUNE_S3_BUCKET", "")

    if not neptune_endpoint or not s3_staging_bucket:
        return {
            "status": "not_configured",
            "message": (
                "Neptune endpoint and S3 staging bucket required. "
                "Set NEPTUNE_ENDPOINT and NEPTUNE_S3_BUCKET env vars."
            ),
            "triple_count": triples_data.get("triple_count", 0),
            "preview": triples_data.get("content", "")[:500],
        }

    try:
        import boto3

        s3 = boto3.client("s3")
        content = triples_data.get("content", "")
        fmt = triples_data.get("format", "ntriples")
        ext = "nt" if fmt == "ntriples" else "jsonld"
        key = f"neptune-staging/graph-data.{ext}"

        s3.put_object(
            Bucket=s3_staging_bucket,
            Key=key,
            Body=content.encode("utf-8"),
        )

        # Trigger Neptune bulk loader
        import urllib.request
        load_url = f"https://{neptune_endpoint}:8182/loader"
        load_payload = json.dumps({
            "source": f"s3://{s3_staging_bucket}/{key}",
            "format": fmt,
            "iamRoleArn": os.environ.get("NEPTUNE_LOAD_ROLE_ARN", ""),
            "region": os.environ.get("AWS_REGION", "us-east-1"),
            "failOnError": "FALSE",
        })

        req = urllib.request.Request(
            load_url,
            data=load_payload.encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())

        return {
            "status": "loading",
            "s3_location": f"s3://{s3_staging_bucket}/{key}",
            "neptune_load_id": result.get("payload", {}).get("loadId", ""),
            "triple_count": triples_data.get("triple_count", 0),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "triple_count": triples_data.get("triple_count", 0),
        }
