# Naming Conventions

Approved naming rules across the Pinnacle platform.

## Tables (Kimball / Addendum B)

- **Facts**: `fct_<grain>` — `fct_client_360`, `fct_fee_attribution`, `fct_advisor_productivity`.
- **Dimensions**: `dim_<concept>` — `dim_client`, `dim_advisor`, `dim_strategy`.
- **Staging**: `stg_<connection>_<source_table>` — one model per source table.
- **Intermediate**: `int_<fact>_<purpose>` — never queried by consumers; stepping stones for marts.

## Columns

- All lower `snake_case`.
- Primary keys end in `_id`; foreign keys carry the same name as their target PK.
- Boolean flags prefixed `is_` or `has_`; never `flg_` or `_yn`.
- Monetary amounts include their unit suffix where ambiguous: `_usd`, `_bps`.

## Schemas (Pinnacle Postgres)

- One schema per business process: `ap`, `billing`, `crm`, `gl`, `hr`, `performance`, `planning`, `portfolio`.
- No tables in `public` for Pinnacle data.

## Iceberg

- Glue databases use `dsa_hub_<scope>_<purpose>` — e.g., `dsa_hub_pinnacle_360`.
- Table names must match `fct_*` or `dim_*` per Kimball.
