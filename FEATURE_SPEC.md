# Feature Spec: ePI Submission Flow (Antigravity ePI Conversion Engine)

**Author:** Product (drafted from `epi-backend` deep-mode code analysis)
**Status:** Draft v1.1 — merged in place from v1.0 against current code
**Date:** 2026-05-06
**Release target:** v2.0.0 (declared in `main.py`)
**Owning service:** `ePI Processing Service` — single-endpoint FastAPI, deployed via Docker (Render / Hugging Face Spaces)
**Scope of this spec:** the **end-to-end submission flow** — upload → parse → FHIR map → validate → auto-fix → fidelity-improve → bundle → diff. Adjacent product surfaces (reviewer UI, multi-tenancy, persistence) are owned by `ENTERPRISE_ROADMAP.md`.

---

## 0. Executive Summary

### What it is

A single FastAPI endpoint, `POST /api/process_stateless`, that turns a Marketing Authorisation Holder's (MAH's) Word/PDF Summary of Product Characteristics (SmPC) into a **validated, fidelity-scored HL7 FHIR R4 Bundle** conforming to the EMA's electronic Product Information Implementation Guide (`hl7.eu.fhir.epil`). One request in, one JSON out — XML, JSON, validation report, fix log, fidelity score, and visual diff included. Designed to fit inside Render's 30-second request budget and integrate with a Supabase-backed frontend.

### Why now

EMA's phased ePI go-live runs Q3 2026 (vaccines, ATC J07) → Q4 2026 (oncology, ATC L01/L04) → broader 2027 rollout. Veeva ships its **AI Agents for RIM** in August 2026, threatening to absorb point-solution ePI conversion inside Vault. The window for a credible self-serve alternative is roughly six months from now.

### Strategic position

The market has three occupied zones — **high-end suites** (Veeva Vault RIM, IQVIA, i4i; six-figure contracts, 6–12 month implementations), **managed services** (Glemser, MT-G, Freyr; 24h–5d SLAs, opaque pricing), and **specialist authoring tools** (READY! for ePI, Docuvera, Datapharm). The fourth zone — **self-serve API for mid-cap MAHs** — is empty. Veeva does not want it; managed-service vendors cannot offer it without cannibalising labour-billing margins; CROs structurally cannot ship it. This product targets that white space.

### Buyer

Head of Regulatory Operations at a mid-cap MAH (€100M–€2B revenue, 20–500 products), with the QA / Validation Lead as gatekeeper and the Director of Labelling at regional CROs as a secondary segment. The buyer wants EMA-deadline coverage, audit-defensibility, and total cost of ownership materially below Veeva's floor price.

### What this spec commits to (v2.0.0)

A single-document conversion endpoint that, on a well-formed QRD-compliant SmPC DOCX, achieves **≥95% validated status, ≥99% recall fidelity, p95 latency <25 s, full audit log per fix**. Hard-gates non-SmPC uploads (PIL/Labelling/non-QRD) with a 422 — auto-detection is reported but the pipeline only accepts SmPC structure today. PIL, Labelling, multi-document product bundles, and multi-jurisdiction support are explicitly out of scope for this version.

### What this spec does NOT commit to

Authentication, persistence, multi-tenant isolation, reviewer UI, e-signatures, multi-language parsing, FDA/Health Canada/PMDA support, live SPOR terminology binding, and async batch processing. Those are tracked in `ENTERPRISE_ROADMAP.md` and become P1/P2 here only where they directly touch the submission flow.

---

## 1. Problem Statement

MAHs must submit electronic Product Information (ePI) — SmPC, PIL, and Labelling — to EMA in HL7 FHIR R4 conforming to `hl7.eu.fhir.epil`. Regulatory and medical-writing teams author these documents in Microsoft Word using the QRD template and archive final versions as PDF. Converting Word/PDF into a structurally valid, profile-conformant FHIR Bundle — preserving 100% of the source content (tables, typography, QRD sub-headers, annexes, labelling blocks) — requires deep HL7 expertise, hand-crafted XHTML narrative hygiene, and multiple passes through the HL7 Java validator.

The cost of doing this manually is measured in **4–10 hours per document per submission** (industry-reported baseline, `COMPETITIVE_ANALYSIS.md`). Every rejection loop with EMA adds regulatory risk, delays market access, and consumes senior regulatory-affairs capacity. Companies without in-house FHIR expertise either outsource conversion at high cost (Glemser 24–48 h SLA, Freyr per-document) or block shipping because the output fails validation.

This product converts a single uploaded SmPC DOCX or PDF into a **validated, fidelity-scored FHIR ePI Bundle in a single API call**, in under 30 seconds, with a structured audit log of every fix applied.

---

## 2. Goals

1. **Conversion coverage (SmPC v1).** Accept DOCX and PDF uploads of SmPC documents and produce a FHIR R4 `Composition` + `Bundle` (XML and JSON) on the first call. Document type is auto-detected from content; non-SmPC uploads are rejected with a 422 and a readable error.
2. **Regulatory validity.** Achieve ≥95% `validated` status (zero HL7 FHIR errors after Phase 1) on well-formed QRD-compliant SmPC DOCX inputs, validated against the official `hl7.eu.fhir.epil` IG.
3. **Content fidelity.** Achieve ≥99% recall fidelity score (source-word-to-output-word match, computed against section narratives only — Composition.text metadata excluded) on standard SmPC documents.
4. **Latency.** Complete the full parse → map → validate → auto-fix → fidelity-improve → bundle pipeline in under 30 s per document. The `MAX_VALIDATION_ITERATIONS = 1` cap in `fhir_validator.py` exists explicitly to keep the synchronous path inside Render's request budget.
5. **Auditability.** Every fix applied by the engine is logged with rule ID, location, and (where available) before/after snippets, and surfaced to the caller as structured `fix_log` JSON, an `issues` list, and a markdown `validation_report_md`.
6. **Renderable output.** The XHTML narrative carries no inline font / size / colour declarations. Typography is supplied by the canonical `static/epi-standard.css` stylesheet, whose URL is returned in the response (`css_href`). Visual hierarchy comes from semantic tags + `epi-narrative` / `epi-annex-title` classes, never from font size variation.

---

## 3. Non-Goals

1. **Non-SmPC documents (this version).** PIL and Labelling parsers exist (`PILStrategy`, `LabellingStrategy` in `doc_parser.py`) but the production endpoint hard-rejects non-SmPC uploads with HTTP 422 (`main.py` lines 71-82). Reason: SmPC is the highest-volume, highest-revenue conversion target, and the SPOR section codes for PIL/Labelling are not yet validated in the mapping table. PIL/Labelling re-enablement is a P1 follow-up and a roadmap item.
2. **Multi-document product bundles.** v1 processes one document per request. Linking SmPC + PIL + Labelling into a single `MedicinalProductDefinition`-rooted bundle is out of scope. A separate "product bundle" orchestration layer will own that.
3. **Persistent storage / user accounts.** The endpoint is `process_stateless`. Storage, versioning, and collaboration live in the Supabase-backed frontend, not in this service. (Note: `ValidationLog.save()` does write `validation_log.json` to disk on each call — this is a known concurrency hazard, see Open Questions.)
4. **Non-EU jurisdictions.** The IG pack pinned in the Dockerfile is `hl7.eu.fhir.epil` only. FDA SPL, Health Canada XML PM, PMDA — all v2 initiatives.
5. **Human-in-the-loop editing.** The service does not return a live editor or patch API. Callers wanting to accept/reject individual fixes must rebuild client-side against `fix_log` and `issues`. The reviewer UI is a separate product surface in the roadmap.
6. **Live SPOR terminology validation.** SPOR / CodeSystem reference errors are filtered from the returned log as `validator configuration issues` (see `_PROFILE_NOT_FOUND_PATTERNS` in `fhir_validator.py`). Real SPOR API binding is a P2 track.
7. **Authentication, rate limiting, multi-tenant isolation, audit persistence.** CORS is `*`; the service trusts its caller. Production hardening lives in the API gateway in front of this service and in the platform roadmap (Sprints 1–3).
8. **Domain extension on `Composition.subject`.** The `http://ema.europa.eu/fhir/extension/domain` extension is currently commented out in `fhir_mapper.py` because the EMA IG validator flags it as an unknown extension. Re-enabling it is gated on validator-package alignment.
9. **Production-grade error taxonomy.** All exceptions surface as `HTTPException(500, str(e))`. Replacing this with typed errors (`PARSE_FAILED`, `MAPPING_FAILED`, `VALIDATOR_UNAVAILABLE`, `FIDELITY_FAILED`) is P1.

---

## 4. User Stories

Ordered by priority. User types are deliberately specific (not "the user").

1. **As a regulatory-operations specialist at a mid-cap MAH**, I want to upload a QRD-formatted SmPC DOCX and get back a validated FHIR Bundle in under 30 seconds, so that I can submit to EMA the same day I finalise the Word draft.
2. **As a regulatory-operations specialist**, I want a clear 422 error when I accidentally upload a PIL or Labelling document, so that I do not waste time wondering why my fidelity score is meaningless.
3. **As a regulatory-operations specialist**, I want a markdown report of every automatic fix applied (`validation_report_md`), so that I can review them with my QA team before I sign off on the submission.
4. **As a medical writer**, I want a visual HTML diff between my source document and the generated FHIR narrative (`diff_html`), so that I can verify no paragraph, table row, or annex line was dropped during conversion.
5. **As a medical writer**, I want tables, bold/italic formatting, bullet lists, and QRD sub-headers (e.g. "4.1 Therapeutic indications") preserved in the narrative XHTML, so that the rendered FHIR output matches the intent of my Word draft.
6. **As a medical writer**, I want Annex I, II, III and Labelling content retained end-to-end, so that nothing in the back half of the document is silently dropped — and I want them rendered with `<h1 class="epi-annex-title">` so the visual hierarchy is correct under the canonical stylesheet.
7. **As a submission manager**, I want a numeric fidelity score (0–100) returned with every successful conversion, so that I can gate submissions on a ≥99% threshold in my workflow tool. I also want the score *suppressed* (returned as `null`, with `fidelity_status: "suppressed_due_to_errors"`) when the bundle is structurally invalid, so that I am never misled into thinking an unfixable bundle is "99% good."
8. **As a backend developer integrating with Supabase**, I want a single JSON response containing `status`, `error_count`, `warning_count`, `info_count`, `summary`, `iterations`, `original_xml`, `xml`, `issues`, `fix_log`, `validation_log_json`, `validation_report_md`, `fidelity_score`, `fidelity_status`, `diff_html`, `bundle_json`, `bundle_xml`, `source_text` (first 2 000 chars), `doc_type`, `sections_count`, and `css_href`, so that my frontend can persist everything from one call.
9. **As a frontend / viewer engineer**, I want a stable URL (`css_href`) for the canonical ePI stylesheet, so that the FHIR narrative — which carries no inline font declarations — renders identically wherever it is shown.
10. **As an SRE**, I want a `/health` liveness endpoint, so that I can run standard Render health checks without touching any external dependency.
11. **(Edge) As a user uploading a document with unescaped `&` characters, empty narrative divs, unclosed `<b>` tags, or HTML-style `<br>` instead of XHTML `<br/>`**, I want the engine to auto-repair these before submission, so that I am not blocked by `XHTML_*` validator errors I did not cause.
12. **(Edge) As a user uploading a malformed or truly unparseable PDF**, I want a clear 500 error with a diagnostic message, so that I know to retry with a DOCX or a clean export.
13. **(Edge) As a user whose document has only one canonical SmPC section anchor (e.g. just a table of contents),** I want the 422 message to tell me how many anchors I have and which sections are expected, so that I can fix my upload without contacting support.
14. **As a Marketing Authorisation Holder's regulatory-operations lead**, I want to opt-in to publishing a converted SmPC bundle behind a stable URL and a scannable QR code, so that an authorised reader (patient, HCP, or QA reviewer) can scan the code and render the human-readable ePI leaflet on any device — without me running my own resolver. The flag is opt-in per request; when it is omitted, the response and pipeline behave exactly as today.
15. **As a Marketing Authorisation Holder's regulatory-operations lead managing a product across versions and languages**, I want to (a) define a product once, (b) attach SmPC / PIL / Labelling / Annex II documents to it in any of the 24 EU languages and any variant (e.g. multiple pack sizes), (c) upload new versions of any document with a two-gate approval workflow (product confirmation + internal QA review) plus a separate agency-decision gate for Type IB / II variations, and (d) hand out one stable QR per product that resolves to an EMA-style portal where a patient can pick their language and document, while the rendered content is always the latest *authorised* version — never a version that has been submitted to the agency but not yet approved. The QR never changes for the lifetime of the product; the content the QR resolves to changes only when an authorised version is explicitly activated.
16. **As a regulatory-operations user uploading an SmPC that contains figures** (chemical structures, dosing diagrams, device-handling pictograms), I want every image to arrive in the ePI bundle as a self-contained `Binary` resource with accessible alt text, so that the bundle validates against the EU IG, renders on the EMA portal exactly as the EMA samples do, and I can see in the fix log which images were converted or need an alt-text review.

---

## 5. Requirements

### Must-Have (P0)

#### P0-1. Stateless single-file conversion endpoint
`POST /api/process_stateless` accepts a `multipart/form-data` file upload (`.docx` or `.pdf`) and returns JSON with every field listed in user story 8. CORS is open (`*`).

*Acceptance criteria:*
- Given a valid SmPC `.docx`, when posted to `/api/process_stateless`, then the response status is 200 and `status ∈ {"validated", "partially_fixed", "errors"}` (`main.py` lines 182-187).
- Given a valid SmPC `.pdf`, when posted, then the same response shape is returned with `doc_type == "SmPC"`.
- Given an unsupported file extension, then the underlying `parse_document` raises `Unsupported file format` and the endpoint returns 500.
- Response time for a 30-page SmPC is <30 s end-to-end on the production Docker image.

#### P0-2. SmPC structural gate (HTTP 422)
The endpoint computes `found_anchors = {s.section_id for s in sections} & {"1","2","3","4","4.1","4.2","4.3","4.4","4.8","5","6","6.1"}` and rejects with HTTP 422 when `len(found_anchors) < 2` (`main.py` lines 71-82). The error `detail` quotes the count and lists the expected anchors.

*Acceptance criteria:*
- Given a PIL or Labelling DOCX, when posted, then a 422 is returned with the diagnostic message and the pipeline does NOT run.
- Given a SmPC DOCX, when posted, then the gate passes (≥2 anchors detected) and the pipeline runs to completion.
- Given a non-pharma document (random Word file), when posted, then 422 is returned.

*Why this exists:* Auto-detection (`DocumentFactory.detect_type`) returns one of `SmPC | PIL | Labelling`, but only the SmPC mapping table and section-grouping logic are validated. Letting non-SmPC uploads through produces meaningless 100% fidelity scores (the FidelityFixer would happily score an empty Composition against an empty-after-skipping source_text).

#### P0-3. Document parsing by strategy
DOCX parsing uses `mammoth` with a `style_map` that promotes Word headings to `h3`–`h6` and unifies underline / hyperlink runs to `<u>`. Images are inlined as base64 `data:` URIs by `convert_image` — this is the parser-level intermediate only; P1-IMG-1 turns them into contained Binary resources at mapping time when the tenant flag is on. PDF parsing uses `pypdf` with HTML-escaped, `<br/>`-joined output. The HTML output of both paths is run through `_sanitize_html_styles` and `_elevate_annex_headers`. Section splitting uses `RegexStrategy` (parameterised by `SMPC_HEADERS`, `PIL_HEADERS`) selected via `DocumentFactory.detect_type`. `LabellingStrategy` is a separate, non-Regex parser keyed on `EXPIRY DATE`, `BATCH NUMBER`, `METHOD OF ADMINISTRATION`, `NAME OF THE MEDICINAL PRODUCT`.

*Acceptance criteria:*
- Given a DOCX containing a table inside Section 4.8, when parsed, then the table HTML is preserved verbatim in `sections[i].text`.
- Given a SmPC with Annex I/II/III, when parsed, Annex III labelling content is accumulated into the `labelling` (or `annex_iii`) section without being re-split by numeric sub-headers — the parser locks into `in_annex = True` once any of `{labelling, annex_i, annex_ii, annex_iii}` is matched (`doc_parser.py` lines 287-298).
- Given content before Section 1, when parsed, it is captured under `section_id == "_preface"`.
- Given a DOCX with `<font face="Arial" color="red">` inline, when parsed, then those attributes are stripped — only `_ALLOWED_STYLE_PROPS` (text-align, table borders, padding, width, vertical-align) survive (`doc_parser.py` lines 24-31).
- Given a paragraph whose visible content is exactly `"ANNEX III"`, when parsed, then it is rewritten as `<h1 class="epi-annex-title">ANNEX III</h1>` (idempotent — already-elevated headings untouched).

#### P0-4. FHIR mapping to Composition + Bundle
`fhir_mapper.create_doc_composition` produces a `Composition` resource with:
- A SPOR-coded `Composition.type` (`100000155538` for SmPC) **plus** a LOINC fallback (`55106-9`, "Clinical Document") to satisfy the validator's "type recommended to come from value set" info-level finding.
- QRD-coded `Composition.section` entries via `SMPC_SECTION_MAPPING`. Sections 4, 5, and 6 are grouped under synthetic parents by `organize_qrd_sections` (Rule 6 of the QRD template).
- XHTML narrative divs wrapped as `<div xmlns="http://www.w3.org/1999/xhtml" class="epi-narrative"><div xmlns="...">…</div></div>`. Annex section titles use `<h1 class="epi-annex-title">`; all other section titles use `<h2>`.
- Tables receive `border="1"` plus an explicit CSS border style on `<table>`, `<td>`, and `<th>` — at mapping time, before validation runs (`_add_table_borders`, `_add_cell_borders`).
- Preface content is embedded directly in `Composition.text.div` (Option B — fully FHIR compliant; no synthetic section code needed).
- The domain extension on `Composition.subject` is currently commented out (validator flags it as unknown; see Non-Goals #8).

`generate_bundle` produces a `Bundle` of `type = "collection"` (because a "document" Bundle cannot legally contain a `List` resource, and Rule 25 of the EMA convention requires a List). The Bundle entries, in order: `List`, `Organization` (placeholder MAH), `MedicinalProductDefinition` (placeholder product), then one or more `Composition` entries.

*Acceptance criteria:*
- Given a SmPC `doc_obj`, when mapped, then `Composition.type.coding[0].code == "100000155538"` and `Composition.type.coding[1].system == "http://loinc.org"`.
- Given a section with mixed prose and tables, when mapped, then `<table>` tags are not HTML-escaped into `&lt;table&gt;` (because `is_html_source` is true).
- Given preface text, when mapped, then it appears in `Composition.text.div` (Option B), not as a numbered section.
- Given a SmPC, when bundled, then `Bundle.type == "collection"` and `Bundle.entry[0].resource.resourceType == "List"`.
- The `Organization` and `MedicinalProductDefinition` resources contain placeholder values that the caller is expected to override downstream (`"Marketing Authorisation Holder (Placeholder)"`, `"Placeholder Product 500mg Tablets"`).

#### P0-5. FHIR validation against EMA ePI IG
`FHIRValidator.validate_string` validates with the HL7 `validator_cli.jar` (pre-baked in the Docker image at `/app/validator_cli.jar`) using `-ig hl7.eu.fhir.epil` and `-version 4.0.1`, with a **300-second subprocess timeout**. Fallbacks: `validator.fhir.org/validate` (`hl7.fhir.r4.core` + `hl7.eu.fhir.epil` IG), then `hapi.fhir.org/baseR4/Bundle/$validate`. Profile-not-found and terminology errors (matched against `_PROFILE_NOT_FOUND_PATTERNS`) are filtered out of the returned log when the HTTP fallbacks run; the Java CLI knows CodeSystems natively, so its results are not filtered.

*Acceptance criteria:*
- Given a well-formed Composition, when validated, errors and warnings come from the official HL7 validator output parsed into `ValidationIssue` objects with severity / location / message / rule (`_parse_json_outcome`, `_parse_xml_outcome`).
- Given a validator log containing "unknown codesystem" or "codesystem is unknown" or "not found in the terminology server", those entries do NOT appear in the final `issues` list returned to the caller.
- When the Java CLI is unavailable or times out, the service transparently falls back to the REST validators; the response shape never changes.
- When all three validators fail, a single `ValidationIssue(severity="Fatal", message="Both validator APIs failed: ...")` is returned and the pipeline reports `status = "errors"`.

#### P0-6. Two-phase pipeline (Phase 1: structural / Phase 2: fidelity)
`run_validation_pipeline` runs:

**Phase 1 — FHIR compliance (≤ `MAX_VALIDATION_ITERATIONS = 1` iteration).** Validate, run `AutoFixer.fix`, log fixes, break. The 1-iteration cap is set deliberately to fit Render's 30 s budget — **an async path can lift this to 3–5 (roadmap Sprint 4)**. Even when `error_count == 0` after the first validator pass, formatting/typography fixes (`_fix_table_borders`, `_fix_qrd_subheaders`, `_fix_missing_linebreaks`) **still run unconditionally** so cosmetic improvements are never skipped.

**Phase 2 — Fidelity improvement (≤ `FidelityFixer.MAX_FIDELITY_ITERATIONS = 5` iterations).** Only runs when `source_text` is supplied. `_compute_fidelity` recall-scores against section narratives only (the first `<text>…</text>` block — Composition.text metadata — is stripped). Strategies, in priority order: `_fix_collapsed_spaces` (FIDELITY_SPACE_INJECTION), `_fix_missing_br_between_blocks` (FIDELITY_BR_INJECTION), `_fix_encoded_entities` (FIDELITY_ENTITY_DECODE), `_fix_stray_h3_wrapping` (FIDELITY_H3_UNWRAP). A candidate is committed only when the new fidelity score strictly exceeds the current one; the loop stops at `FIDELITY_TARGET = 99.0` or when no strategy can improve further.

Phase 2's fix log is appended to the `ValidationLog` as a synthetic `ValidationRun` carrying forward Phase 1's last error / warning / info counts (no re-validation needed because Phase 2 fixes never alter FHIR resource structure).

*Acceptance criteria:*
- Given a narrative `<div>` without `xmlns`, after the pipeline runs, it contains `xmlns="http://www.w3.org/1999/xhtml"` (XHTML_NS_FIX).
- Given `<br>` in the input, after pipeline, it is `<br/>` (XHTML_SELF_CLOSING).
- Given `&` outside an entity, after pipeline, it is `&amp;` (XHTML_AMPERSAND_ESCAPE).
- Given an "unknown element" validator error for `<table>`, the table is **not** removed (`_fix_invalid_xhtml_elements` short-circuits on `table/tr/td/th/tbody/thead`).
- Given a document scoring 93% initially, after Phase 2, the score is either ≥ 99% or monotonically higher than the starting value.
- No Phase 2 fix alters FHIR resource structure (profile, coding, references) — every strategy operates only on XHTML inside narrative divs.
- Every fix is idempotent — running the same fix twice on the same input produces the same output.

#### P0-7. Fidelity-score suppression on invalid bundles
The endpoint surfaces `fidelity_score` only when `error_count == 0`; otherwise it is `null` and `fidelity_status == "suppressed_due_to_errors"`. When `error_count == 0`, `fidelity_status == "available"`.

*Acceptance criteria:*
- Given a bundle with 0 errors and source_text supplied, then `fidelity_score` is a float 0–100 and `fidelity_status == "available"`.
- Given a bundle with ≥ 1 errors after Phase 1, then `fidelity_score is None` and `fidelity_status == "suppressed_due_to_errors"`.
- Rationale: a recall-based metric on a structurally invalid bundle misleads users into thinking an invalid document was processed successfully.

#### P0-8. Static-styling contract (no inline fonts in narrative)
The XHTML narrative MUST NOT contain inline `font-family`, `font-size`, `color`, `bgcolor`, or class attributes outside `_ALLOWED_CLASS_NAMES = {"epi-annex-title", "epi-narrative"}`. Allowed style props are limited to layout primitives (text-align with values `center | right | justify`, table border / padding / width). Visual hierarchy comes from semantic tags + CSS, NOT from font-size variation. The canonical stylesheet at `static/epi-standard.css` enforces 11 pt Times New Roman everywhere; the response's `css_href` field tells the caller where to load it.

*Acceptance criteria:*
- Given a DOCX with `<span style="font-family: Calibri; color: red">`, when processed, then the output XHTML contains no `font-family`, no `color`, and no `Calibri`.
- Given a `<font face="Arial">` element, then the `<font>` tag is unwrapped and its content kept (`_sanitize_html_styles` step 1).
- The endpoint response always contains `"css_href": "/static/epi-standard.css"`.
- The static stylesheet is mounted at `/static` only when the directory exists (`main.py` lines 37-40).

#### P0-9. Visual diff
`diff_engine.generate_html_diff` produces an HTML span-wrapped diff with `.diff-equal`, `.diff-add`, `.diff-del` classes between the plain source text and the fixed XML. Both sides are normalized via `clean_for_diff(preserve_formatting=True)` before being word-split. List items are rendered as bullet text; table cells receive forced spacing.

*Acceptance criteria:*
- Given any successful conversion, `diff_html` is a non-empty string of HTML spans.
- Given a diff failure, the field is returned as an empty string and the overall request still succeeds (`main.py` `try/except`).

#### P0-10. Status taxonomy
Final `status` is exactly one of:
- `"validated"` — `error_count == 0`.
- `"partially_fixed"` — `error_count > 0` AND `error_count < first_run.error_count`.
- `"errors"` — neither of the above (no improvement).

#### P0-11. Liveness
`GET /health` returns `{"status": "healthy"}` without touching any external dependency.

#### P0-12. CORS
The service allows all origins / methods / headers (`allow_origins=["*"]`) for integration with the Supabase frontend behind an API gateway in production.

---

### Should-Have / Nice-to-Have (P1)

#### P1-1. Progress callback / Server-Sent Events stream
`run_validation_pipeline` already accepts a `progress_callback`; expose it as an SSE endpoint so the frontend can show "Phase 1 / iter 1 — 12 errors, 4 warnings…" live. Stream events: `phase_1_start`, `phase_1_validator_running`, `phase_1_errors`, `phase_1_fixing`, `phase_2_start`, `phase_2_score`, `phase_2_complete`, `done`.

#### P1-2. Configurable fidelity target
Allow callers to pass `fidelity_target` in the multipart body (default 99.0) so non-regulatory use cases can opt for faster / lower-quality modes. Lower bound 0; upper bound 100; cap iterations at the FidelityFixer hard limit.

#### P1-3. Re-enable PIL & Labelling
Remove the 422 gate and prove out PIL + Labelling end-to-end. Requires (a) verified SPOR section codes for PIL, (b) a tested end-to-end fixture set, and (c) a non-SmPC analogue of the QRD section grouping. Until then, the 422 stays as a quality gate.

#### P1-4. Repair-engine integration (ghost-header detection)
`repair_engine.run_intelligent_repair` (ghost-header detection + HTML hygiene) exists but is **not invoked anywhere in the production pipeline**. Wire it in as a pre-mapping step. Specifically the "Section 4 header buried in Section 3" case is already implemented — low-effort lift, real fidelity improvement on malformed sources.

#### P1-5. Download-link responses
For large docs, return pre-signed object-storage URLs for `bundle_xml`, `bundle_json`, `validation_report_md` instead of embedding them in JSON. Reduces response size from ~MB to ~KB and unblocks the Supabase row-size limit (see Open Questions).

#### P1-6. Structured error taxonomy
Replace the catch-all `HTTPException(500, str(e))` with typed errors: `PARSE_FAILED`, `MAPPING_FAILED`, `VALIDATOR_UNAVAILABLE`, `FIDELITY_FAILED`, `INVALID_FILE_TYPE`. Each comes with a stable error code, an HTTP status, and a documentation URL.

#### P1-7. PDF fidelity parity
Current PDF parsing (pypdf → escaped text) loses tables and formatting because pypdf's text extraction does not preserve table structure. Add a `doc_warning` in the response when a PDF is uploaded that says "PDF parsing is lossy; DOCX produces materially higher fidelity scores."

#### P1-8. Fix `validation_log.json` concurrency hazard
`ValidationLog.save()` writes `validation_log.json` to `project_dir` on every call. In a stateless concurrent service this means two parallel requests overwrite each other's logs. Either remove the write entirely (the response already contains `validation_log_json`), or write to a per-request temp path.

#### P1-9. Reconcile main.py vs test_e2e.py source_text construction
`main.py` includes `labelling` in `source_text` (because Annex III content accumulates into it) but `test_e2e.py` excludes it. The intent in `main.py` is correct; update the test to match, or document the decision so test failures don't masquerade as bugs.

#### P1-PUB-1. Opt-in publication flag on the conversion endpoint
**Given** the existing `POST /api/process_stateless` contract, **when** the caller submits the multipart body with an additional `publish: true` field **and** the pipeline completes with `status ∈ {"validated", "partially_fixed"}`, **then** the response gains two additive fields:
- `publication_id` — a deterministic UUID v5 derived from `(bundle_sha256, tenant_id)` so re-publishing the same bundle for the same tenant returns the same identifier (idempotency, see P1-PUB-3).
- `qr_svg` — a base64-encoded SVG QR code that encodes the canonical render URL `https://epi.antigravity.eu/r/{publication_id}` (or the configured public base for non-prod environments).

When `publish` is absent or `false`, the response is byte-identical to v2.0.0 — the 21-field shape in user story 8 is preserved (no field renames, no removals, no semantic drift). When `publish: true` is sent **and** `status == "errors"`, the endpoint returns **HTTP 409** with body `{"detail": "cannot publish a non-conforming bundle", "code": "PUBLISH_REJECTED_INVALID_BUNDLE"}` (see CLAUDE.md §10 #12). The conversion result itself is not persisted in this 409 branch; the caller gets the same in-memory pipeline output via a separate `publish: false` retry.

The feature is gated by a per-tenant feature flag `publication_v1_enabled`, default off (CLAUDE.md §5.7). For v1 demo, the flag is read from the `PUBLICATION_TENANTS_ALLOWLIST` environment variable; the production flag store lands in Sprint 1 alongside the tenant config table.

#### P1-PUB-2. Public render endpoint for the human-readable leaflet
**Given** an existing `publication_id`, **when** any caller issues `GET /api/v1/render/{publication_id}`, **then** the service returns the rendered XHTML leaflet for that bundle with content-type `application/xhtml+xml; charset=utf-8`, a `<link rel="stylesheet" href="/static/epi-standard.css">` in the `<head>`, and a footer block disclosing `bundle_sha256` (truncated to 12 chars), `validator_outcome`, `published_at` (ISO-8601 UTC), and `correlation_id`. The endpoint is unauthenticated by design (mixed-audience use case — patient/HCP/QA, see user story 14).

When the `publication_id` does not exist, the endpoint returns **HTTP 404** with body `{"detail": "publication not found", "code": "PUBLICATION_NOT_FOUND"}`. When the publication has been revoked (P1-PUB-4 audit event `publication.revoked`), the endpoint returns **HTTP 410 Gone** with body `{"detail": "publication revoked", "code": "PUBLICATION_REVOKED", "revoked_at": "<ISO-8601 UTC>"}`. The render output is byte-deterministic from the stored bundle — no transforms, no fixers, no rewrites at scan time (CLAUDE.md §10 #9). v1 is single-language: the rendered language is the language of the originally-uploaded SmPC. Multi-language negotiation is deferred to P2-PUB-LANG (see Open Question §8 #11).

A `<meta name="publication-stability" content="preview">` tag and a small "preview" watermark on the rendered page MUST be present until P2-PUB-LANG ships — this is the line between demo and packaging-grade publication and is enforced by a contract test.

#### P1-PUB-3. Idempotency of publication
**Given** a bundle that has already been published once for a given tenant, **when** the caller re-submits the same source DOCX with `publish: true` and the same authenticated tenant, **then** the resulting `publication_id` is byte-identical to the prior publication, the `qr_svg` is byte-identical, and the stored XHTML payload is byte-identical. Re-publishing produces no new row in the publication store — it is a no-op apart from an `audit.publication.republished` event linked to the existing `publication_id`. The check is implemented by deriving `publication_id = uuid5(NAMESPACE_PUBLICATION, f"{tenant_id}:{bundle_sha256}")`. A unit test asserts `publish(publish(x)) == publish(x)`.

#### P1-PUB-4. Audit trail for publication lifecycle
Every publication lifecycle event MUST produce an append-only audit row with the structured fields below (CLAUDE.md §4.1):
- `publication.created` — emitted on first successful publish. Fields: `actor_id`, `tenant_id`, `publication_id`, `bundle_sha256`, `correlation_id`, `created_at` (ISO-8601 UTC server clock), `language`, `validator_outcome`, `fidelity_score`.
- `publication.served` — emitted on each successful `GET /api/v1/render/{id}`. Fields: `publication_id`, `served_at`, `correlation_id`. **No** IP, user-agent, or other identifying scanner data is logged (GDPR posture per CLAUDE.md §4.5; aggregate scan_count is computed by counting these rows, not by storing per-scan PII).
- `publication.republished` — emitted when an idempotent re-publish is observed. Fields: `actor_id`, `tenant_id`, `publication_id`, `correlation_id`, `republished_at`.
- `publication.revoked` — emitted when an admin action takes the publication out of service. Fields: `actor_id`, `tenant_id`, `publication_id`, `correlation_id`, `revoked_at`, `reason`. The publication row is **not** physically deleted (CLAUDE.md §10 #2); the resolver returns 410 Gone.

For v1 demo, audit rows are written to the existing in-memory audit log structure (which already exists for validation events) plus the SQLite publication store. The Postgres-backed hash-chained audit landed in Sprint 2 supersedes both.

---

#### P1-IMG-1. Images as contained Binary resources
**Given** a DOCX whose parser output contains `<img src="data:<mime>;base64,…">` elements, **when** the tenant is on `IMAGE_BINARIES_TENANTS_ALLOWLIST` and the document is mapped by `fhir_mapper.create_doc_composition(…, embedder=ImageEmbedder())`, **then**:
- each distinct image (by SHA-256 of its final bytes) becomes exactly one `Binary` in `Composition.contained` with `id = "img-" + sha256(final_bytes)[:32]`, `contentType` = final MIME type, `data` = base64 of the final bytes — in first-appearance document order;
- every `<img>` in `Composition.text.div` (preface) and every `Composition.section[…].text.div` is rewritten to `<img src="#<id>" alt="<alt>"/>` carrying **exactly** the attributes `src` and `alt` (width/height/style/class stripped — styling is the stylesheet's job, CLAUDE.md §9.3);
- one `Composition.extension` per Binary with `url = http://ema.europa.eu/fhir/StructureDefinition/ext-epi-image-reference` and `valueReference.reference = "#<id>"`, in the same order as `contained`;
- no `data:` URI remains anywhere in `original_xml`, `xml`, `bundle_xml`, `bundle_json`, or `source_text`;
- `ImageEmbedder.process` is idempotent — `process(process(html)) == process(html)` — and a no-op input is returned byte-equal (CLAUDE.md §5.5, §7.3); an untouched (undecodable) image is audited once per `(section, tag)`, not once per pass;
- v1 scope is one document per request: `generate_bundle` with several documents would attach the request's whole Binary set to every Composition (tracked under P2-1 multi-document bundles);
- an `<img>` whose `data:` URI cannot be base64-decoded is left untouched and flagged `IMG-FORMAT-UNSUPPORTED` (never mangle content we cannot read).

*Acceptance criteria:*
- Given `tests/fixtures/synthetic_smpc_images.docx` (4 `<img>`, 3 distinct images, fig1 == fig4), when posted with an allow-listed `tenant_id`, then `xml` and `bundle_xml` each contain exactly 3 `<contained><Binary>` blocks, 4 `<img>` tags, each `src` resolves to a contained `id`, and `data:image` appears nowhere in the response.
- Given the same upload twice, then the set of `(id, contentType, sha256(data))` is identical (CLAUDE.md §4.4).
- Given the flag is off or `tenant_id` is not allow-listed, then the response is byte-identical to v2.0.0 behaviour (inline `data:` URIs, no `contained`, no `IMG-*` rows).
- Given the FHIR XML serialiser, then `<text>` precedes `<contained>`, which precedes `<extension url="…ext-epi-image-reference">`, which precedes `<status>` (FHIR DomainResource element order).
- Given the `validator_cli.jar` against `hl7.eu.fhir.epil`, then the Binary-bearing SmPC produces **no new errors** relative to the image-free sibling fixture. HTTP-fallback runs are flagged as such (CLAUDE.md §10 #12).

*Why this exists:* the EU IG (`EUEpiComposition.contained`: "Images in ePI Composition documents included as contained binary resources"), the HL7 ePI Tech Style Guide and the EMA validated sample EPI-25-100 all use contained Binary + `#id`. A `data:` URI is FHIR-legal but not what EMA emits, and no fixture has ever exercised it against the validator.

#### P1-IMG-2. Non-web-safe image formats are rasterised to PNG
**Given** an image whose MIME type is not in `WEB_SAFE_MIME = {image/png, image/jpeg, image/svg+xml}` (Word commonly yields `image/tiff`, `image/bmp`, `image/gif`, `image/x-emf`, `image/x-wmf`), **when** it is embedded, **then** it is converted to PNG before hashing/embedding; `Binary.contentType == "image/png"`, `Binary.id` is the hash of the **PNG** bytes, and a `IMG-RASTERISE` audit row records `before = <source mime> sha256=<12> bytes=<n>` and `after = image/png sha256=<12> bytes=<n>`.
- Pillow-readable formats (TIFF, BMP, GIF, WebP, …) convert in-process via Pillow.
- EMF/WMF convert via LibreOffice Draw headless (`soffice --headless --convert-to png`), one invocation per image with a private `-env:UserInstallation` each (no profile-lock collisions under concurrency), sharing one 15 s budget per request (the process group is killed on timeout; images past the budget fall back to IMG-FORMAT-UNSUPPORTED), 300 DPI derived from the metafile frame, longest side capped at 2400 px (Open Question 19). *Implementation note 2026-09-08: batching all metafiles into a single invocation is a follow-up optimisation; the per-request budget guarantee is the same.*
- Every PNG — converted or re-encoded — passes through `normalise_png()` (decode → re-save, no ancillary text/time chunks, fixed encoder settings) so the bytes are deterministic for a pinned Pillow version.
- SVG passes through untouched **only** if it is plain UTF-8 text with no `<script`, no `on*=` attributes, no external `href`/`xlink:href`/`url()`/`@import` and no `<!ENTITY`; otherwise the offending constructs are stripped (`defang_svg`) and the result is rasterised, so no script or external fetch ever reaches the renderer. An SVG that fails the check and conversion is preserved and flagged `IMG-SVG-UNSAFE` **and** `IMG-FORMAT-UNSUPPORTED`.
- Any raster whose header declares more than 50 megapixels is refused before decoding (`MAX_DECODE_PIXELS`) and treated as a conversion failure — a decompression-bomb guard, not a quality limit.
- If conversion raises `ImageConversionError` (unsupported format, converter timeout, LibreOffice missing), the **original bytes are preserved** as a Binary with their real MIME type, the `<img>` still points at it, and an `IMG-FORMAT-UNSUPPORTED` row is written. Nothing is dropped (CLAUDE.md §4.1 Complete).
- A final payload > 1 MiB writes an `IMG-SIZE-LARGE` row (informational; no cap in v1 — Open Question 22).

*Acceptance criteria:*
- Given a TIFF `data:` URI, when embedded, then the Binary is `image/png`, its payload starts with the PNG magic bytes, and its id equals the hash of the PNG bytes.
- Given three runs on the same TIFF, then the PNG sha256 is identical each time.
- Given a converter that raises, then the Binary keeps `image/tiff`, the bytes are unchanged, and `IMG-FORMAT-UNSUPPORTED` is present while `IMG-RASTERISE` is absent.
- Given a PNG or JPEG input, then no `IMG-RASTERISE` row exists and the bytes are unchanged.
- Given the production Docker image, when a real ChemDraw EMF fixture (`tests/fixtures/images/chemdraw_sample.emf`, to be supplied by a design partner) is processed, then the Binary is `image/png` and the end-to-end time stays < 30 s (P0-1 budget). Test skips if the fixture is absent.

#### P1-IMG-3. Alt text is mandatory — preserve, else placeholder + flag
**Given** an `<img>` with a non-empty `alt`, **when** embedded, **then** the alt is preserved verbatim. **Given** an `<img>` with no `alt` or an all-whitespace `alt`, **then** `alt="Figure N"` is emitted, where N is the 1-based ordinal of that `<img>` among all `<img>` elements the embedder has seen in document order (preface first, then sections in QRD order), and an `IMG-ALT-MISSING` row is written with `location = <section_id>`.

*Acceptance criteria:*
- Given `synthetic_smpc_images.docx` (fig2 in section 4.2 has no alt), then exactly one `IMG-ALT-MISSING` row exists, its `location` is `4.2`, and the emitted tag is `alt="Figure 2"`.
- Given alt text present, then no `IMG-ALT-MISSING` row exists for that image.
- Given `alt=""`, then it is treated as missing.
- The placeholder language is English in v1 (Open Question 20).

#### P1-IMG-4. Audit evidence, feature flag, and contract preservation
- **Audit.** Every image transformation writes an `ImageAction(rule, location, description, before_snippet, after_snippet)`. `main.py` prepends these to `fix_log` as `{"iteration": 0, "rule", "description", "location"}` rows — the same four keys as validator fixes; `iteration 0` means "mapping phase, before Phase 1". Rule IDs: `IMG-EMBED` (one per `<img>`, even when deduplicated; description names the Binary id, MIME, byte count, sha256[:12] and `dedup=true|false`), `IMG-RASTERISE`, `IMG-ALT-MISSING`, `IMG-FORMAT-UNSUPPORTED`, `IMG-SVG-UNSAFE`, `IMG-SIZE-LARGE`.
- **Flag.** `IMAGE_BINARIES_TENANTS_ALLOWLIST` (comma-separated tenant slugs), read in `main.py` exactly like `PUBLICATION_TENANTS_ALLOWLIST`. Default off. Removal of the flag follows CLAUDE.md §5.7 (two design partners × 1 week, passing acceptance test, ≥ 50 audited runs).
- **Contract.** The response keeps exactly the 21 keys of user story 8 (23 with `publish: true`). No key is added, renamed, or retyped. `fix_log` remains a list of four-key dicts. `validation_log_json` additionally carries the same actions as an `iteration: 0` run whose `fixes_applied` include `before_snippet` / `after_snippet` (source MIME, sha256[:12], byte counts) — the four-key `fix_log` rows cannot hold that evidence (CLAUDE.md §4.1 Complete). Flag-off: nothing is added.
- **Pipeline.** Embedding is a mapping-time transform; Phase 1 → Phase 2 order and all constants are untouched (CLAUDE.md §5.3). `_compute_fidelity` strips tags before tokenising, so images contribute zero words; the image-bearing fixture must score within 0.5 of its image-free sibling (CLAUDE.md §5.8).
- **Side effect (documented).** `ImageEmbedder.process` rewrites `doc["sections"][i]["text"]` **in place** so `source_text` and `generate_bundle` see `#id` references without a second embedding pass. `generate_bundle(doc_list, embedder=…)` reuses the same embedder; `process` on already-rewritten text is a no-op.

*Acceptance criteria:*
- Given the fixture, then `fix_log` contains 4 × `IMG-EMBED`, 1 × `IMG-ALT-MISSING`, 1 × `IMG-RASTERISE`, 0 × `IMG-FORMAT-UNSUPPORTED`, all with `iteration == 0` and a non-empty `location`.
- Given flag on or off, then `set(response.keys()) == the 21 baseline fields`.
- Given the flag off, then no `IMG-*` row exists and `xml` still contains `data:image/`.
- Given `original_xml`, then it already contains the 3 Binaries (validated as shipped).

---

### Future Considerations (P2)

- **P2-1. Multi-document product bundles.** Compose SmPC + PIL + Labelling + MedicinalProductDefinition + Organization in a single Bundle with cross-references. Requires a separate orchestration endpoint.
- **P2-2. Multi-IG support.** FDA SPL, Health Canada XML PM, PMDA profile packs alongside `hl7.eu.fhir.epil`. Affects the `FHIRValidator.EMA_EPI_IG` constant and the `RMS_SPOR_CODES` registry — design the `mapper` layer for pluggability now even if we only ship EMA.
- **P2-3. Live SPOR terminology validation.** Integrate with EMA's SPOR API (with nightly local cache + outage fallback), stop filtering CodeSystem errors. Will surface real terminology binding mismatches that today are silently dropped.
- **P2-4. Incremental / patch API.** Accept an edited Composition and re-validate only the changed sections. Pairs with the reviewer UI on the roadmap.
- **P2-5. OCR fallback for image-heavy PDFs.** Route to an OCR path (Tesseract or hosted) before `read_pdf` when text extraction returns < N words per page.
- **P2-6. Async / queued path.** Move the Java validator to a dedicated worker pool; lift `MAX_VALIDATION_ITERATIONS` to 3–5 in async; expose `POST /v1/jobs` and `GET /v1/jobs/:id`.
- **P2-7. Domain extension re-enablement.** When the EMA IG validator package recognises `http://ema.europa.eu/fhir/extension/domain`, restore the extension on `Composition.subject` (currently commented in `fhir_mapper.py`).
- **P2-8. Variation packages (Type IB, II).** Accept a prior-submission bundle reference and emit a delta. This is what Reg-Ops actually does day-to-day; today the spec only covers fresh MAA submissions.
- **P2-PUB-PORTAL. EMA-style portal at scan time.** *(Supersedes the original P2-PUB-LANG, which was scoped only to language negotiation.)* The QR resolves to a server-rendered HTML portal at `GET /api/v2/p/{publication_id}` modelled on the EMA PLM Portal (`https://plm-portal.ema.europa.eu/ePIDetails/...`): product header at the top, language picker with Apply + Export buttons, left-hand collapsible tree of documents grouped by `doc_type` (SmPC / Annex II / Labelling / PL) with one row per (doc_type, variant), right-hand pane rendering the currently-selected document's XHTML narrative styled by `/static/epi-standard.css`. URL pattern: `/api/v2/p/{publication_id}` (Accept-Language default), `/api/v2/p/{publication_id}?lang=fr` (explicit), `/api/v2/p/{publication_id}?lang=fr&doc_id={uuid}` (specific document). Server-side rendered so the QR works on any device with no JavaScript required for basic operation; minimal vanilla JS for collapse/expand and language picker. Language detection precedence at upload time: **QRD template metadata → filename convention → body-text heuristic (`langdetect`) → user-override picker** — and the source of the detected language is surfaced in the UI so a reg-ops user can override before publishing. The `<meta name="publication-stability" content="preview">` watermark and visible preview banner remain on every rendered page until both P2-PUB-PROD ships **and** ≥ 1 design partner has approved the rendered output for their use case. CLAUDE.md §10 #9 enforced: stored XHTML is served byte-for-byte at scan time; no transforms.

- **P2-PUB-VERSION. Versioned content with a stable QR.** *(New.)* The data model splits "what the QR is" from "what the QR resolves to." The QR is stable for the lifetime of the publication — it encodes `publication_id`, which is derived once at product creation. The *content* the QR resolves to is the **current active version** of each `(doc_type, language, variant)` triple under that publication. New entities: `Product` (the medicine, tenant-owned, names the product), `ProductPublication` (the stable QR handle, one per product), `Document` (a `(doc_type, language, variant)` slot under the publication), `DocumentVersion` (the actual content; many per Document; `Document.current_version_id` is the activation pointer). Idempotency key: `publication_id = uuid5(NAMESPACE, f"{tenant_id}:{product_canonical_key}")` where `product_canonical_key` is a tenant-scoped identifier set at Product creation. Two-gate approval workflow on every upload: **Gate 1** — product mapping confirmation (UI shows detected match; user accepts or picks a different product); **Gate 2** — internal QA approval (user reviews validator outcome, fidelity, and diff vs current version, picks Approve+Activate / Approve only / Reject). `Document.current_version_id` updates atomically and emits a `document.version_activated` audit row. Re-uploading byte-identical bytes is a no-op (returns the existing version row; emits `document.version_re_uploaded`).

- **P2-PUB-VAR. Variation lifecycle (Type IA / IB / II) and dual-gate activation.** *(Supersedes the placeholder P2-PUB-VARIATIONS.)* Adds Gate 3 (agency decision) on top of the P2-PUB-VERSION workflow for any non-initial version. `DocumentVersion` gains five columns: `variation_type` (`INITIAL` / `TYPE_IA` / `TYPE_IA_IN` / `TYPE_IB` / `TYPE_II`), `agency_submission_status` (`NOT_REQUIRED` / `NOT_SUBMITTED` / `SUBMITTED` / `APPROVED` / `REJECTED` / `WITHDRAWN` / `EXPIRED_WITHOUT_OBJECTION`), `agency_submission_reference`, `agency_submitted_at`, `agency_decision_received_at`. Activation rule: `Document.current_version_id` may move to a new version only when the version's `internal_approval_status == 'APPROVED'` **and** the agency-status gate is satisfied for its `variation_type` — `TYPE_IB` requires `APPROVED` or `EXPIRED_WITHOUT_OBJECTION`, `TYPE_II` requires `APPROVED`, `TYPE_IA` is satisfied at `SUBMITTED`. The `EXPIRED_WITHOUT_OBJECTION` state for Type IB is recorded only by an explicit user attestation that the 30-day window has closed without objection — never by elapsed-time automation alone (ALCOA+ attribution). Daily cron surfaces notifications at 28d / 30d for Type IB and at 60d for Type II; notifications are informational, never trigger state changes. Audit events: `variation.classified`, `variation.submitted_to_agency`, `variation.agency_decision_recorded`, `variation.activated`, `variation.deactivation_blocked`. Full design in `outputs/VARIATION_LIFECYCLE_DESIGN.md`. Until `agency_submission_status` clears the gate for a given version, the QR continues to resolve to the previously-authorised version (CLAUDE.md §10 #12 enforced).

- **P2-PUB-PDF. Server-side PDF export of the rendered portal.** *(New.)* `GET /api/v2/p/{publication_id}/export.pdf?lang=fr&doc_id={uuid?}` produces a deterministic PDF via WeasyPrint over the same XHTML rendering used by the live portal. Each PDF page carries the preview banner (until the P2-PUB-PORTAL banner gate releases), the integrity footer (truncated `bundle_sha256`, `validator_outcome`, `version_number`, `published_at`, `correlation_id`), page numbers, and optionally a small QR in the corner of each page so a printed PDF can be re-scanned. `weasyprint==60.x` is pinned in `requirements.txt`; bumps require regenerated test baselines.

- **P2-PUB-AUDIT. Postgres + hash-chained audit.** *(New, replaces the SQLite v1 demo store.)* Move all publication storage and audit logging from SQLite to Postgres. New Postgres-native schema for `Product`, `ProductPublication`, `Document`, `DocumentVersion`, and a `publication_audit` table where every row carries `prev_row_hash` and `payload_hash`, making the audit log tamper-evident (each row binds itself to the prior row's payload, so any modification of historical rows invalidates every subsequent row's hash). Retention policy column-enforced (`retention_until ≥ now + 7 years`, CLAUDE.md §4.1). Adapter pattern so unit tests can keep running on an in-memory store. Alembic migrations from day one. Audit-bundle export endpoint that returns the chain for a publication as a verifiable JSON document. Required prerequisite for any of P2-PUB-PORTAL / P2-PUB-VERSION / P2-PUB-VAR shipping — the SQLite v1 store cannot model the v2 schema and is also ephemeral on the Render filesystem.

- **P2-PUB-PROD. Production-grade resolver SLA.** Deploy the resolver behind an EU-resident CDN (Cloudflare or equivalent) with 99.9% uptime; add monitoring, rate limiting, DDoS posture; bring the resolver into CSV scope (URS / FS / DS / IQ / OQ / PQ). Required before any customer prints the QR on Annex III artwork. Pairs with P2-PUB-PORTAL (multi-language) and P2-PUB-VAR (agency-status gating). Blocked on engagement of a CSV / Validation Lead (currently in backlog).
- **P2-IMG-1. Vector-preserving EMF/WMF → SVG.** Replace PNG rasterisation for EMF/WMF with an SVG conversion (LibreOffice `--convert-to svg` + sanitisation) so chemical structures stay lossless, per the IG's "SVG preferred". Requires an SVG sanitiser with its own idempotency tests and a Reg SME check that EMA renders SVG.
- **P2-IMG-2. Localised and caption-derived alt text.** Emit the placeholder in the document language (`Abbildung N`, `Figure N`, …) using the language detected for P2-PUB-PORTAL, and propose alt text from an adjacent caption paragraph for reviewer acceptance (never auto-accepted — labelling content, CLAUDE.md §10 #9).
- **P2-IMG-3. Image QA surface.** Reviewer UI listing each Binary with thumbnail, source MIME, conversion path, alt status; pairs with the P2-4 incremental API so alt text can be corrected without re-uploading the DOCX.

---

## 6. Success Metrics

### Leading Indicators (first 30 days post-launch)

- **Adoption rate.** % of connected MAH tenants submitting ≥ 1 SmPC/week. Target: 60% in 30 days. Source: Supabase `conversions` table — distinct `tenant_id` over a 7-day window.
- **Validation-pass rate.** % of requests returning `status == "validated"`. Target: ≥ 80% on DOCX, ≥ 50% on PDF. Source: response-field logs.
- **Fidelity ≥ 99% rate.** % of requests with `fidelity_score >= 99.0` (and therefore `fidelity_status == "available"`). Target: ≥ 85% on SmPC DOCX. Source: response logs.
- **422 reject rate.** % of uploads rejected by the SmPC structural gate. Target: < 5% (high reject rate signals the documentation hasn't communicated the SmPC-only constraint clearly enough).
- **p95 latency.** Target: < 25 s; hard ceiling: 30 s (Render budget). Source: request-duration telemetry.
- **5xx error rate.** Target: < 1%. Source: Render edge logs.

### Lagging Indicators (60–90 days post-launch)

- **Per-document conversion cost in human hours.** Baseline: 4–10 h manual (industry-reported, see `COMPETITIVE_ANALYSIS.md`). Target: < 15 minutes of human review per document.
- **EMA rejection rate (downstream).** Of bundles produced by this service and submitted to EMA, % rejected for structural non-conformance. Target: < 2%.
- **Expansion / attach rate.** % of MAH tenants that upgrade from trial to paid within 60 days.
- **Support-ticket reduction.** Tickets tagged "FHIR validation help" vs. manual-conversion baseline. Target: 50% reduction within 90 days.
- **NPS among regulatory-ops users.** Target: ≥ 40 after 90 days.

### Measurement Specification

All leading metrics rely on Supabase persisting the JSON response fields (`status`, `iterations`, `error_count`, `fidelity_score`, `fidelity_status`, request duration, `tenant_id`, `doc_type`). Evaluation windows: 7, 30, and 90 days post-launch. Dashboards owned by the data team; alerts on p95 latency and 5xx rate page on-call.

---

## 7. Code Traceability Matrix

Every P0 requirement is grounded in a specific module / function. Reviewers use this table to spot drift between spec and code at PR time.

| Requirement | File | Symbol(s) / Line(s) |
|---|---|---|
| P0-1. Endpoint contract | `main.py` | `process_stateless` (lines 43–239); CORS `add_middleware` (27–33) |
| P0-2. SmPC 422 gate | `main.py` | lines 71–82 (`_SMPC_ANCHOR_IDS`, `found_anchors`, `HTTPException(422)`) |
| P0-3. DOCX/PDF parsing | `doc_parser.py` | `read_docx`, `read_pdf`, `RegexStrategy`, `LabellingStrategy`, `DocumentFactory.detect_type`, `_sanitize_html_styles`, `_elevate_annex_headers` |
| P0-4. FHIR mapping | `fhir_mapper.py` | `create_doc_composition`, `organize_qrd_sections`, `create_section`, `generate_bundle`, `RMS_SPOR_CODES`, `SMPC_SECTION_MAPPING` |
| P0-5. Validator | `fhir_validator.py` | `FHIRValidator.validate_string`, `_parse_json_outcome`, `_parse_xml_outcome`, `_filter_config_issues`, `_PROFILE_NOT_FOUND_PATTERNS` |
| P0-6. Two-phase pipeline | `fhir_validator.py` | `run_validation_pipeline`, `AutoFixer.fix`, `FidelityFixer.improve`, `_compute_fidelity`, `MAX_VALIDATION_ITERATIONS = 1`, `FIDELITY_TARGET = 99.0`, `MAX_FIDELITY_ITERATIONS = 5` |
| P0-7. Fidelity suppression | `main.py` | lines 215–217 (`fidelity_score if error_count == 0 else None`, `fidelity_status`) |
| P0-8. Static-styling contract | `doc_parser.py`, `fhir_mapper.py`, `static/epi-standard.css`, `main.py` | `_ALLOWED_STYLE_PROPS`, `_ALLOWED_CLASS_NAMES`, `epi-narrative` div wrapping, `epi-annex-title` h1 elevation, `CSS_HREF` |
| P0-9. Visual diff | `diff_engine.py` | `generate_html_diff`, `clean_for_diff`, `extract_section_narratives` |
| P0-10. Status taxonomy | `main.py` | lines 182–187 |
| P0-11. Liveness | `main.py` | `health_check` (line 242) |
| P0-12. CORS | `main.py` | `CORSMiddleware(allow_origins=["*"], …)` |
| P1-PUB-1. Publish flag (additive response) | `main.py`, `publication_service.py` | `process_stateless` accepts `publish: bool = Form(False)`; appends `publication_id` and `qr_svg` keys when publish path runs; `publication_service.publish_bundle()`; tenant flag check via `PUBLICATION_TENANTS_ALLOWLIST` |
| P1-PUB-2. Render endpoint | `main.py`, `publication_service.py` | `GET /api/v1/render/{publication_id}` route; `publication_service.lookup()`; XHTML response with `epi-standard.css` link, `<meta name="publication-stability" content="preview">`, and footer disclosure block |
| P1-PUB-3. Publication idempotency | `publication_service.py`, `qr_generator.py` | `publication_service.derive_publication_id()` using `uuid5(NAMESPACE_PUBLICATION, f"{tenant_id}:{bundle_sha256}")`; `qr_generator.svg_for_url()` deterministic by URL |
| P1-PUB-4. Audit trail | `publication_service.py` | `_audit_emit()` records `publication.created`, `publication.served`, `publication.republished`, `publication.revoked`; SQLite audit table `publication_audit` |
| P1-IMG-1. Contained Binary embedding | `image_embedder.py` (new), `fhir_mapper.py` | `ImageEmbedder.process`, `BinaryRecord`, `binary_id_for`, `EXT_IMAGE_REFERENCE`; `create_doc_composition(…, embedder=)` attaches `contained` + `extension:imageReference`; `generate_bundle(…, embedder=)`; `_json_to_xml` emits `<contained><Binary>` |
| P1-IMG-2. Rasterisation | `image_embedder.py`, `Dockerfile`, `requirements.txt` | `WEB_SAFE_MIME`, `to_png`, `normalise_png`, `_libreoffice_to_png`, `ImageConversionError`; `Pillow` pin; `libreoffice-draw` + `fonts-dejavu-core` layers |
| P1-IMG-3. Alt text | `image_embedder.py` | ordinal counter in `ImageEmbedder`, `IMG-ALT-MISSING` |
| P1-IMG-4. Audit / flag / contract | `image_embedder.py`, `main.py` | `ImageAction`; `IMAGE_BINARIES_TENANTS_ALLOWLIST` check next to the publish allowlist; `fix_log` prepend at `iteration 0`; `source_text` built after `create_doc_composition` |
| P2-PUB-AUDIT. Postgres + hash-chained audit | `publication_service.py` (refactor), `alembic/` (new), `models/` (new) | `Publication`, `Document`, `DocumentVersion` SQLAlchemy models; `publication_audit` table with `prev_row_hash` + `payload_hash` columns; `audit_chain_export()`; adapter pattern for in-memory test store |
| P2-PUB-PORTAL. EMA-style portal at scan time | `portal_renderer.py` (new), `main.py` (new v2 routes) | `GET /api/v2/p/{publication_id}`; server-side HTML template with left tree + language picker + right pane; `Accept-Language` negotiation; collapse/expand vanilla JS; language detection precedence: QRD metadata → filename → heuristic → user-override |
| P2-PUB-VERSION. Versioned content with stable QR | `models/`, `publication_service.py` | `Product`, `ProductPublication`, `Document`, `DocumentVersion` entities; `Document.current_version_id` activation pointer; two-gate upload workflow; idempotent re-upload of byte-identical bytes |
| P2-PUB-VAR. Variation lifecycle (Type IA / IB / II) | `variation_service.py` (new) | `DocumentVersion.variation_type` + four `agency_*` columns; `_can_activate()` with dual-gate rule; `_emit_audit('variation.*')`; daily cron for reminders; `EXPIRED_WITHOUT_OBJECTION` attested-only state |
| P2-PUB-PDF. Server-side PDF export of the rendered portal | `pdf_exporter.py` (new) | `GET /api/v2/p/{publication_id}/export.pdf`; WeasyPrint over the same XHTML the portal serves; preview banner + integrity footer + page numbers; optional per-page QR |

A failing test in `test_e2e.py` (or `tests/contract/test_publication.py` for P1-PUB-*, `tests/contract/test_portal.py` for P2-PUB-*, or `tests/unit/test_image_binaries.py` + `tests/contract/test_image_contract.py` for P1-IMG-*) against any of these symbols should be treated as a P0 / P1 / P2 regression.

---

## 8. Open Questions

1. **(Blocking — Engineering)** `MAX_VALIDATION_ITERATIONS = 1` is set to stay inside Render's 30 s budget, but limits the engine's ability to re-validate after structural fixes. Should we move validation to an async background worker (breaks the stateless contract) or accept single-iteration Phase 1 in v1 and lift it in the async path (Sprint 4)?
2. **(Blocking — Regulatory SME)** `SMPC_SECTION_MAPPING` is annotated *"Codes above 4.8, 6.1 etc need validation against official SPOR list."* Until verified these could trigger EMA-side rejection. Need a Reg SME to sign off on the mapping before v1 GA.
3. **(Blocking — Legal / Platform Security)** CORS is `*`. For production, what's the auth model — API key, JWT, Supabase service role? Owner: platform security. Sprint 1 of the roadmap commits to API keys as an interim step.
4. **(Blocking — Engineering)** `ValidationLog.save()` writes to `project_dir/validation_log.json` on every request — a real concurrency hazard for a stateless concurrent service. Two parallel requests will overwrite each other's logs. Decision needed: remove the write, or per-request temp path.
5. **(Non-blocking — Data)** How do we persist `validation_log_json` and `bundle_xml` in Supabase without blowing row limits? JSONB column vs. object storage with URL? Pairs with P1-5.
6. **(Non-blocking — Design)** Should `diff_html` be rendered client-side with the service's CSS conventions (`.diff-equal`, `.diff-add`, `.diff-del`), or should the service also return a self-contained stylesheet (parallel to `css_href`)?
7. **(Non-blocking — Engineering)** `repair_engine.py` is authored but un-integrated. Confirm P1-4 schedule.
8. **(Non-blocking — QA)** Canonical reference set of "gold" documents — `valid_test.docx` and `Joenja_QRD_Final_Template_Sachin-v2.docx` are referenced in `test_e2e.py`, but we do not have an EMA-signed-off corpus. Action: secure ≥ 5 customer-supplied SmPCs as the v1 acceptance suite.
9. **(Non-blocking — Engineering)** `main.py` includes `labelling` in `source_text` for fidelity scoring; `test_e2e.py` excludes it. Reconcile (P1-9).
10. **(Non-blocking — Engineering)** The `Composition.subject` `domain` extension is commented out because the validator flags it. Track when the `hl7.eu.fhir.epil` IG package recognises it, then restore.
11. **(Blocking — Regulatory + Product before any customer prints the QR on artwork)** P1-PUB v1 ships single-language with a `<meta name="publication-stability" content="preview">` tag and a "preview" watermark on the rendered page. The watermark must remain until P2-PUB-LANG (multi-language negotiation) and P2-PUB-PROD (production-grade resolver SLA) ship. Need a Reg SME + design-partner QA Lead sign-off on (a) the exact watermark wording, (b) the language-list JSON shape inside the publication store, and (c) the deprecation path from preview to packaging-grade.
12. **(Non-blocking — Privacy / DPO)** `publication.served` audit rows do not log scanner IP or user-agent (GDPR posture). Confirm with DPO that the aggregate `scan_count` derived from row counting is acceptable for analytics — and that the absence of per-scan PII is documented in the DPA.
13. **(Non-blocking — Security)** The `GET /api/v1/render/{publication_id}` endpoint is unauthenticated by design (mixed-audience scan use case). Need rate-limiting policy and DDoS posture before public exposure beyond design partners — covered by P2-PUB-PROD.
14. **(Blocking — Regulatory SME, before P2-PUB-VAR ships)** The Type-II agency review window in EMA practice is procedure-dependent (60 / 90 / 180 days, with clock-stops). What default window do we expose in the reminder schedule, and how do we let the regulatory-ops user override per-version? Need a Reg SME sign-off on the default and the override UI. Source: VARIATION_LIFECYCLE_DESIGN.md "Out of scope (v2)".
15. **(Non-blocking — Engineering)** Should the `EXPIRED_WITHOUT_OBJECTION` state for Type IB require a verifying user separate from the user who submitted the variation (four-eyes principle)? Cheap to add; modest UX cost; arguably required by GxP rigour. Decide before P2-PUB-VAR engineering starts.
16. **(Blocking — Product + Reg SME, before P2-PUB-PORTAL ships)** Language detection precedence: QRD metadata → filename → heuristic → user-override picker. What is the minimum confidence threshold for the body-text heuristic before we accept it without prompting? Source: P2-PUB-PORTAL.
17. **(Non-blocking — UX)** When a regulatory-ops user uploads a new document for an existing product, the system must propose a `(doc_type, language, variant)` triple. How do we surface "variant" detection — free-text input, dropdown of known variants for that product, or a hybrid? Source: P2-PUB-VERSION upload flow.
18. **(Non-blocking — Engineering)** v1 endpoints (`POST /api/process_stateless`, `GET /api/v1/render/{publication_id}`) remain as a back-compat layer alongside the new `/api/v2/...`. How long do we commit to keeping v1 live before deprecation, and what triggers the deprecation announcement? Default per CLAUDE.md §5.9: 6 months from v2 GA, with `X-API-Deprecated` and `X-API-Sunset-Date` headers throughout the deprecation window.
19. **(Blocking — Regulatory SME, before P1-IMG ships to a design partner)** Rasterisation parameters for EMF/WMF (default 300 DPI, longest side ≤ 2400 px). Does EMA impose a resolution, colour-space or size limit on ePI images? The IG only says "clear and easy to read" and "no resizing by the stylesheet". Source: P1-IMG-2.
20. **(Non-blocking — Regulatory + UX)** Placeholder alt text `Figure N` is English. For non-English SmPCs, do we localise the word (`Abbildung`, `Figura`, …) from the detected document language, or keep a language-neutral token? Source: P1-IMG-3, P2-IMG-2.
21. **(Non-blocking — Engineering)** We emit `Composition.extension:imageReference` because the EU IG package defines it (0..\*), but the EMA validated sample EPI-25-100 does not use it. Confirm the validator is silent; if it warns, drop it following the §9.4 domain-extension precedent and record the decision here. Source: P1-IMG-1 D6.
22. **(Non-blocking — Engineering + Reg SME)** No hard cap on Binary payload size in v1 (informational `IMG-SIZE-LARGE` at 1 MiB). What is EMA's bundle size limit for portal ingestion, and does Render's 30 s budget survive a 20-figure SmPC? Source: P1-IMG-2.
23. **(Non-blocking — QA)** We need one real ChemDraw-exported EMF and one WMF from a design partner for `tests/fixtures/images/`. The synthetic corpus covers TIFF only. Source: P1-IMG-2 AC 5.

---

## 9. Timeline Considerations

**Hard deadlines.** EMA's ePI submission mandate phases in through Q3 2026 (vaccines / ATC J07) and Q4 2026 (oncology / ATC L01/L04), with broader CAP rollout in 2027. Any MAH customer using this tool for a product dossier with a 2026 Q3 filing date is a contractual driver for v1 readiness by **2026 Q2** (end of June). The competitive horizon is **August 2026**, when Veeva ships AI Agents for RIM.

**Dependencies.**
- Docker image rebuild pipeline must pre-fetch the `hl7.eu.fhir.epil` IG package (already wired via the Dockerfile dummy-validation step). Any IG version bump requires a Docker rebuild and cache bust.
- `validator.fhir.org` and `hapi.fhir.org/baseR4/Bundle/$validate` availability — our HTTP fallbacks, not under our control. If both are down and `validator_cli.jar` is missing, the service fails open with a single Fatal `ValidationIssue`.
- Supabase schema readiness to accept the 21-field response (incl. `fidelity_status`, `css_href`).

**Suggested phasing.**

- **Phase A (now → 4 weeks).** Ship P0-1 through P0-12 as currently built. Harden the Dockerfile pipeline, add contract tests against `test_e2e.py`'s reference documents, wire Render + Supabase integration. Resolve blocking Open Questions (#1 async path, #2 SPOR sign-off, #3 auth, #4 log concurrency).
- **Phase B (5–8 weeks).** Ship P1-1 (SSE progress), P1-4 (wire `repair_engine`), P1-6 (typed errors), P1-8 (log concurrency fix), P1-9 (test reconciliation). Address PDF fidelity parity (P1-7).
- **Phase C (9–16 weeks).** Begin P2 architecture for multi-document bundles and multi-IG support — design `mapper` and `validator` layers for pluggability now. Pair with the platform roadmap's Sprint 3–4 (variation packages, async path, reviewer UI).

---

*End of spec.*
