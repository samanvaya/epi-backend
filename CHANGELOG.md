# Changelog

All notable changes to the Antigravity ePI Backend are recorded here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Operating rules for this file (see `CLAUDE.md` §4.3, §6.6, §8): every code change carries a CHANGELOG entry under the next semantic version, in the same PR. No exceptions.

---

## [Unreleased]

### Added
- (track in-flight additions here)

### Changed
- 

### Deprecated
- 

### Removed
- 

### Fixed
- 

### Security
- 

---

## [2.0.0] — 2026-04-15

First version under the documented operating contract (`CLAUDE.md` v1.0). The behaviour below describes the current production endpoint at `POST /api/process_stateless`. The earlier Hugging Face deployment variant (`main_HF.py`) is not covered.

### Added
- Single stateless conversion endpoint `POST /api/process_stateless` (`main.py`).
- 21-field JSON response: `status`, `error_count`, `warning_count`, `info_count`, `summary`, `iterations`, `original_xml`, `xml`, `issues`, `fix_log`, `validation_log_json`, `validation_report_md`, `fidelity_score`, `fidelity_status`, `diff_html`, `bundle_json`, `bundle_xml`, `source_text` (first 2 000 chars), `doc_type`, `sections_count`, `css_href`.
- SmPC structural gate at HTTP 422 — rejects uploads with fewer than 2 canonical SmPC anchor sections (`main.py` lines 71–82).
- DOCX parsing via `mammoth` and PDF parsing via `pypdf`, with strategy-pattern section splitting (`SmPCStrategy`, `PILStrategy`, `LabellingStrategy`).
- Aggressive HTML style sanitiser (`_sanitize_html_styles` in `doc_parser.py`) enforcing the static-styling contract (`_ALLOWED_STYLE_PROPS`, `_ALLOWED_CLASS_NAMES = {'epi-annex-title', 'epi-narrative'}`).
- Annex header elevation — bare "ANNEX I/II/III" lines wrapped in `<h1 class="epi-annex-title">`.
- FHIR Composition + Bundle synthesis (`fhir_mapper.py`) with SPOR-coded `Composition.type` (`100000155538` for SmPC) plus LOINC `55106-9` fallback.
- `Bundle.type = "collection"` containing a `List` resource at entry 0, followed by placeholder `Organization` and `MedicinalProductDefinition`.
- Two-phase validation pipeline (`fhir_validator.py`):
  - Phase 1 — FHIR compliance via HL7 `validator_cli.jar` against `hl7.eu.fhir.epil`, with `validator.fhir.org` and `hapi.fhir.org` HTTP fallbacks. Capped at `MAX_VALIDATION_ITERATIONS = 1` for the synchronous endpoint to fit Render's 30 s budget.
  - Phase 2 — Fidelity improvement loop (`FidelityFixer`) up to `MAX_FIDELITY_ITERATIONS = 5`, targeting `FIDELITY_TARGET = 99.0`.
- `AutoFixer` rule library: `XHTML_NS_FIX`, `XHTML_SELF_CLOSING`, `XHTML_AMPERSAND_ESCAPE`, `XHTML_UNCLOSED_TAG`, `XHTML_EMPTY_NARRATIVE`, `XHTML_INVALID_ELEMENT`, `XHTML_DUPLICATE_NS`, `UI_FORMAT_TABLE_BORDERS`, `UI_FORMAT_SUBHEADERS`, `UI_FORMAT_LINEBREAKS`.
- `FidelityFixer` rule library: `FIDELITY_SPACE_INJECTION`, `FIDELITY_BR_INJECTION`, `FIDELITY_ENTITY_DECODE`, `FIDELITY_H3_UNWRAP`. All idempotent.
- Visual HTML diff with `.diff-equal`, `.diff-add`, `.diff-del` spans (`diff_engine.py`).
- Fidelity-score suppression — `fidelity_score = null` and `fidelity_status = "suppressed_due_to_errors"` when `error_count > 0`.
- Status taxonomy: `validated` / `partially_fixed` / `errors`.
- Canonical 11 pt Times New Roman stylesheet (`static/epi-standard.css`); narrative carries no inline font declarations; URL returned as `css_href`.
- `GET /health` liveness endpoint.
- Markdown validation report (`validation_report_md`) for human review.
- Operating contract `CLAUDE.md` v1.0.
- PRD `FEATURE_SPEC.md` v1.1 with code-traceability matrix.
- Strategy docs: `ENTERPRISE_ROADMAP.md`, `COMPETITIVE_ANALYSIS.md`, `MARKETING_COMPETITIVE_BRIEF.md`, `CAMPAIGN_PLAN.md`.
- Test scaffolding under `tests/` (`unit/`, `contract/`, `validation/`, `fixtures/`).

### Known issues (carried into [Unreleased])
- `ValidationLog.save()` writes `validation_log.json` to `project_dir` on every call — concurrency hazard for a stateless service. (FEATURE_SPEC P1-8.)
- `repair_engine.py` ghost-header detection authored but un-wired into the pipeline. (P1-4.)
- `main.py` includes `labelling` in `source_text` but `test_e2e.py` excludes it — test/code drift. (P1-9.)
- `Composition.subject` `domain` extension currently commented out because the validator flags it as unknown. (P2-7.)
- `SMPC_SECTION_MAPPING` codes above 4.8 / 6.1 not yet validated against the live SPOR list. (Open Question §8 #2.)
- CORS is `*`; no auth, no rate limiting, no tenant isolation. (Open Question §8 #3; roadmap Sprint 1.)
- Catch-all `HTTPException(500, str(e))` leaks internal exception text. (P1-6.)

---

[Unreleased]: ./compare/v2.0.0...HEAD
[2.0.0]: ./releases/tag/v2.0.0
