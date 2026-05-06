# Contract tests

Tests that lock the public API shape. These should fail loudly on any unintended change to the response or status codes.

## What lives here

- The 21-field response shape — every field present, correct type, optional/required flag honoured.
- Status taxonomy: `validated` / `partially_fixed` / `errors`.
- HTTP status codes: 200 on completion, 422 on the SmPC structural gate (`main.py` lines 71–82), 500 on unexpected failure.
- `fidelity_score` / `fidelity_status` coupling — score suppressed (returned as `null`) when `error_count > 0`, with `fidelity_status == "suppressed_due_to_errors"`.
- `css_href == "/static/epi-standard.css"`.
- `Bundle.type == "collection"` and the entry order: List → Organization → MedicinalProductDefinition → Composition.
- `Composition.type.coding` contains both the SPOR coding (`100000155538` for SmPC) AND the LOINC fallback (`55106-9`).
- `<div>` narrative wrappers carry `xmlns="http://www.w3.org/1999/xhtml"` and the appropriate `epi-narrative` / `epi-annex-title` classes.
- 422 detail message quotes the anchor count and lists expected anchor IDs.

## What contract failures mean

A failing contract test should never be "fixed" by changing the contract.

Either the change is **intentional** — in which case the same PR must update:
1. `FEATURE_SPEC.md` §5 (acceptance criteria) and §7 (traceability matrix).
2. `CHANGELOG.md` under the next semantic version.
3. The response-shape rule in `CLAUDE.md` §5.1 must be honoured (additions only; deprecation policy for changes).

…or it's a **regression** and the code reverts.

There is no third option.

## Test entry points

```
test_response_shape.py          # All 21 fields present, types correct
test_status_codes.py            # 200 / 422 / 500 paths
test_status_taxonomy.py         # validated / partially_fixed / errors
test_fidelity_suppression.py    # null on errors, available on success
test_bundle_structure.py        # type + entry order + List presence
test_composition_coding.py      # SPOR + LOINC dual coding
test_xhtml_narrative.py         # xmlns, classes, allowed styles
test_smpc_gate.py               # 422 with diagnostic message
```
