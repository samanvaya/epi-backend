# Fixtures (golden corpus)

DOCX / PDF inputs used by the contract and end-to-end tests, plus their `.expected.json` baseline.

## Required fixtures (CLAUDE.md §7.2)

- `joenja_qrd_template.docx` — copy from `~/Downloads/Joenja_QRD_Final_Template_Sachin-v2.docx` (referenced in `test_e2e.py`'s default path).
- `valid_test.docx` — currently in repo root; move it here.
- ≥ 3 anonymised customer-supplied SmPCs covering the variation matrix:
  - **simple** — short SmPC, minimal tables, no Annex content.
  - **complex_tables** — section 4.8 with multiple multi-page tables.
  - **substantial_annex** — meaningful Annex I / II / III content + Labelling block.

## Expected-baseline format

Each fixture has a sibling `<name>.expected.json` capturing the response baseline:

```json
{
  "status": "validated",
  "error_count": 0,
  "warning_count": 0,
  "info_count": 0,
  "iterations": 1,
  "fidelity_score": 99.4,
  "fidelity_status": "available",
  "doc_type": "SmPC",
  "sections_count": 18
}
```

The contract test (`tests/contract/test_response_shape.py`) and `test_e2e.py` compare actual response fields to these baselines. Mismatches fail the build with a clear diff.

## Anchor: regression rule

Per `CLAUDE.md` §5.8, **any PR that lowers the recorded `fidelity_score` for any fixture is rejected by default**. Acknowledged regressions require:

1. Explicit note in the PR description naming which fixture(s) regressed and why.
2. Updated `<name>.expected.json` in the same PR.
3. Approval from Syo before merge.
4. CHANGELOG entry under the relevant version's "Changed" or "Fixed" section.

## Anonymisation checklist (before committing a customer fixture)

- [ ] Product name (brand + INN) replaced with a placeholder.
- [ ] Batch numbers, lot numbers, expiry dates replaced.
- [ ] MAH name and address replaced.
- [ ] Author and contact details stripped.
- [ ] Document control numbers, internal version codes stripped.
- [ ] Any Member-State-specific identifiers (e.g. AT/H/xxxx/xxx/Yr) replaced.

If a fixture cannot be safely anonymised, do not commit it. Use it locally only.
