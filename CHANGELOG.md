# Changelog

All notable changes to the Antigravity ePI Backend are recorded here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Operating rules for this file (see `CLAUDE.md` §4.3, §6.6, §8): every code change carries a CHANGELOG entry under the next semantic version, in the same PR. No exceptions.

---

## [Unreleased]

### Added
- **P1-PUB-1.** Optional `publish: bool = Form(False)` parameter on `POST /api/process_stateless`. When `true` and `status ∈ {"validated", "partially_fixed"}`, the response gains two **additive** keys: `publication_id` (deterministic UUID v5 derived from `(tenant_id, bundle_sha256)`) and `qr_svg` (base64-encoded SVG QR code that resolves to the public render URL). When `publish` is absent or `false`, the 21-field v2.0.0 response shape is byte-identical (no field renames, no removals, no semantic drift). When `publish: true` and `status == "errors"`, returns HTTP 409 `{"code": "PUBLISH_REJECTED_INVALID_BUNDLE"}` (CLAUDE.md §10 #12 — never publish a non-conforming bundle).
- **P1-PUB-2.** New route `GET /api/v1/render/{publication_id}` returns the rendered XHTML leaflet for the stored bundle: `application/xhtml+xml; charset=utf-8`, `<link rel="stylesheet" href="/static/epi-standard.css">` in `<head>`, footer block disclosing truncated `bundle_sha256`, `validator_outcome`, `published_at` (ISO-8601 UTC), and `correlation_id`. 404 on unknown id; 410 Gone on revoked. Render output is byte-deterministic from the stored bundle — no fixers, no rewrites at scan time (CLAUDE.md §10 #9).
- **P1-PUB-3.** Idempotency contract: `publish(publish(x)) == publish(x)`. Re-publishing a bundle for the same tenant returns the same `publication_id`, the same `qr_svg`, and emits a `publication.republished` audit event linked to the existing publication row (no duplicate row).
- **P1-PUB-4.** Audit trail for publication lifecycle — `publication.created`, `publication.served`, `publication.republished`, `publication.revoked` — written to `publication_audit` table in the SQLite v1 store. `publication.served` rows log NO scanner IP or user-agent (GDPR posture, CLAUDE.md §4.5); aggregate `scan_count` is derived by row-count.
- New module `qr_generator.py` — wraps `qrcode` to emit deterministic SVG bytes from a URL.
- New module `publication_service.py` — SQLite-backed write-once publication store keyed by `publication_id`. Schema is forward-compatible with the Sprint 2 Postgres + object-storage migration.
- New tests under `tests/contract/test_publication.py` (HTTP shape, status codes, additive-only response, 409 / 404 / 410 paths) and `tests/unit/test_qr_idempotency.py` (publication_id derivation, SVG byte determinism, `f(f(x)) == f(x)` for the publish path).
- New env vars: `PUBLICATION_TENANTS_ALLOWLIST` (comma-separated tenant slugs allowed to use the publish path), `PUBLICATION_DB_PATH` (defaults to `data/publications.db`), `PUBLICATION_PUBLIC_BASE_URL` (defaults to `http://localhost:8000` in dev).
- "Preview" watermark + `<meta name="publication-stability" content="preview">` on every rendered page until P2-PUB-LANG (multi-language) and P2-PUB-PROD (production resolver SLA) ship. The watermark is the gate between demo and packaging-grade (FEATURE_SPEC §8 Q11).
- New user story 14 in FEATURE_SPEC §4.
- Spec entries P1-PUB-1..4 (FEATURE_SPEC §5), P2-PUB-LANG and P2-PUB-PROD (§5 P2), and traceability rows in §7.
- New `requirements.txt` entry: `qrcode==7.4.2`.

### Changed
- `requirements.txt` — `qrcode` added (additive; no version bumps to existing pins).
- The two-phase pipeline (FHIR compliance → Fidelity) is **unchanged**. Publication is a Phase 3 *post-bundle artefact* layer that runs only when `publish: true` is passed (CLAUDE.md §5.3 protected — Phase ordering and existing constants untouched).

### Deprecated
- 

### Removed
- 

### Fixed
- 

### Security
- The render endpoint is unauthenticated by design (mixed-audience: patient / HCP / QA reviewer). v1 is gated by per-tenant feature flag `publication_v1_enabled` (default off) and limited to design-partner tenants in `PUBLICATION_TENANTS_ALLOWLIST`. Public exposure beyond design partners is gated on P2-PUB-PROD (rate-limiting + DDoS posture + CDN).

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
