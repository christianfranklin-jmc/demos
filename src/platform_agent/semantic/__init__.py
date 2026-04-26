"""Per-connection semantic graph (002-dsa-hub-pinnacle).

Per Q2: each connection owns its own graph + product registry +
activity log. Storage is SQLite locally (~/.dsa-hub/connections/<id>/)
or DynamoDB single-table when deployed. See research.md R2.
"""
