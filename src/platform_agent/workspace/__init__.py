"""Per-tab workspace abstraction (002-dsa-hub-pinnacle).

A Workspace owns 1..N Connections, all keyed by the existing per-tab
session UUID (Q1 — see specs/002-dsa-hub-pinnacle/spec.md Clarifications).
Server-side state is in-memory only; durable per-connection assets live
in `platform_agent.semantic` per-connection stores.
"""
