# Validation tests (CSV — Computer System Validation)

Customer-runnable Operational Qualification (OQ) and Performance Qualification (PQ) scripts.

**Empty until Sprint 4** (see `ENTERPRISE_ROADMAP.md` §3 — "Market Moment, May 27 → Jun 14"). When populated, scripts here will:

- Be parametrisable against a customer's own tenant (env vars for tenant ID, API key, expected behaviour thresholds).
- Produce a customer-brandable validation report (Markdown + PDF).
- Map every test case to a P0 / P1 requirement in `FEATURE_SPEC.md` (traceability matrix entry).
- Be runnable by a QA Lead without developer assistance — single command, machine-checkable output.

Until then this directory is a placeholder so `CLAUDE.md` §7.1's promise resolves to a real path.

## Planned structure

```
tests/validation/
├── README.md (this file)
├── urs/                 # User Requirements Specification, customer-editable
├── fs/                  # Functional Specification, derived from FEATURE_SPEC.md
├── iq/                  # Installation Qualification — runbook + evidence capture
├── oq/                  # Operational Qualification — parametrised scripts
├── pq/                  # Performance Qualification — scenario-based with customer data
├── traceability_matrix.csv   # URS → FS → DS → test case → evidence
└── validation_report_template.md
```

## Why this is a separate directory from `unit/` and `contract/`

`unit/` and `contract/` exist for *engineering* regression. `validation/` exists for *regulatory* evidence. The QA Lead at a customer site should be able to run `validation/` against their own tenant and produce a report they hand to an EMA inspector — without engineering review, without internal credentials, without our acknowledgement.
