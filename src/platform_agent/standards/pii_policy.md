# PII / PCI / PHI Tagging Policy

**v1 status (Q4): informational only.** The platform does NOT auto-detect
candidate PII columns, surface tag banners on TTYD responses, log tag
touches in the activity log, or mask/block at any query path. This page
documents the categories and expected handling so a team can plan their
own enforcement.

## Categories (informational)

| Tag | Examples | Expected handling (v2+) |
|-----|----------|------------------------|
| PII | client name, email, address, phone, advisor email | TTYD masks tagged columns by default; explicit unmask requires a recorded rationale |
| PCI | account number, payment card data | TTYD refuses queries selecting tagged columns unless an override is recorded |
| PHI | n/a for Pinnacle | reserved for healthcare verticals |
| Internal | employee SSN, salary, comp band | role-scoped access enforced by the deployed-mode RBAC layer |

## v2+ roadmap

- Auto-detect candidate columns by name + sample-value patterns.
- TTYD response banners listing tagged columns touched.
- Activity log records tag touches per query / per provisioning run.
- Configurable mask / block enforcement.
