"""Provisioning orchestrator (002-dsa-hub-pinnacle).

Runs the 7-agent DAG (schema → pipeline → model → quality → mapping
→ {semantic, delivery}) that materializes a PRD into a registered
Iceberg Data Product. See specs/002-dsa-hub-pinnacle/research.md R6.
"""
