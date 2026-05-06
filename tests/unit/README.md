# Unit tests

Pure-function tests. No I/O, no validator subprocess, no network. Should complete in seconds.

## What lives here

- `doc_parser.py` sanitisers (`_sanitize_html_styles`, `_elevate_annex_headers`, `_sanitize_style_attr`).
- `doc_parser.py` strategies (`SmPCStrategy.parse`, `PILStrategy.parse`, `LabellingStrategy.parse`, `DocumentFactory.detect_type`).
- `fhir_mapper.py` helpers (`create_section`, `organize_qrd_sections`, `_json_to_xml`, `_xml_attr`).
- `fhir_validator.py` `AutoFixer.*` rule strategies (one test file per rule, named `test_autofixer_<rule>.py`).
- `fhir_validator.py` `FidelityFixer._fix_*` strategies (one test file per rule).
- `fhir_validator.py` `_compute_fidelity` recall scorer.
- `diff_engine.py` helpers (`clean_for_diff`, `extract_section_narratives`).

## Required tests for every fixer (CLAUDE.md §7.3)

Three test cases at minimum per rule:

1. **Idempotency.** `f(f(x)) == f(x)` for at least three inputs: a clean input, an already-fixed input, and an edge case (empty string, deeply nested, mixed content).
2. **No-op safety.** An input that does not trigger the rule is returned unchanged (byte-equal, including whitespace).
3. **Effect.** An input that should trigger produces the expected output, with the expected `FixAction.rule` recorded.

## Naming convention

```
test_<module>_<function>.py
test_<module>_<function>_<edge_case>.py
```

Examples:

```
test_doc_parser_sanitize_html_styles.py
test_doc_parser_sanitize_html_styles_idempotent.py
test_fhir_validator_autofixer_xhtml_ns_fix.py
test_fhir_validator_fidelity_space_injection.py
```

## Forbidden in this directory

- No reads from `tests/fixtures/` — that's `contract/` and `test_e2e.py` territory. Unit tests use small inline fixtures defined inside the test file.
- No `subprocess` calls (the validator). Mock `validator_cli.jar` invocation if the unit under test needs it.
- No HTTP. Mock `httpx.Client`.
