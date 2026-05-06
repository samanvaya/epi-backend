# Tests

Test taxonomy as defined in `CLAUDE.md` §7.1.

| Folder | What it tests | Cadence |
|---|---|---|
| `unit/` | Pure functions — sanitisers, fixers, diff helpers, fidelity scoring | Every PR, fast |
| `contract/` | The 21-field response shape, status taxonomy, status codes (200, 422, 500) | Every PR |
| `validation/` | OQ / PQ scripts customers can re-run for their own validation package | Sprint 4+, on-demand |
| `fixtures/` | Golden DOCX corpus + sibling `.expected.json` baselines (data, not code) | Read by all the above |

End-to-end tests live in `../test_e2e.py` and exercise the full pipeline against the golden corpus.

## Running

```bash
# All tests
python3 -m pytest tests/

# Just unit tests (fast)
python3 -m pytest tests/unit/

# Contract tests
python3 -m pytest tests/contract/

# E2E against the default fixture
python3 test_e2e.py
```

## Adding a new test

Per `CLAUDE.md` §6 step 4, **the test comes before the implementation**. Every Given/When/Then in `FEATURE_SPEC.md` §5 should map to at least one test in this directory. Every fixer rule needs an idempotency test (§7.3) before it ships.

## What this directory does NOT contain

- No production code. Module imports go upward (`from doc_parser import …`), never the other way.
- No customer-supplied source documents that haven't been anonymised. Strip product names, batch numbers, MAH identifiers before committing a fixture.
- No secrets — never paste API keys, tokens, or credentials, even for fixture services.
