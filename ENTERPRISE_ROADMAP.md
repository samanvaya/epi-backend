# Antigravity ePI Backend — 8-Week Enterprise Readiness & Market Leadership Roadmap

**Prepared:** 2026-04-14
**Window:** April 14 → June 14, 2026 (8 weeks)
**Objective:** Turn the current stateless FastAPI prototype into an enterprise-ready product that can be procured, validated, and put into GxP production by a mid-cap MAH in 30 days, and be the defensible category leader for "self-serve ePI for mid-cap MAHs" before Veeva's AI Agents August 2026 GA and EMA's end-of-August Q3 go-live.
**Upstream docs:** `FEATURE_SPEC.md`, `COMPETITIVE_ANALYSIS.md`, `MARKETING_COMPETITIVE_BRIEF.md`
**Codebase state referenced:** `main.py`, `fhir_validator.py`, `repair_engine.py`, `doc_parser.py`, `fhir_mapper.py`, `Dockerfile` (as of 2026-04-14).

---

## 1. Market Leadership Thesis (the actual gap)

### 1.1 What the competitive analysis really shows

Eight vendors touch ePI conversion. Their footprints cluster in three zones:

- **High-end platform zone** — Veeva Vault RIM, i4i, IQVIA. Six-figure contracts, 6–12 month implementations, wide scope (RIM + labelling + submissions). They own the top-50 pharma segment.
- **Managed-service zone** — Glemser, MT-G, Freyr, ProductLife, Accenture. Human-in-the-loop conversion, 1–5 day SLAs, opaque pricing, relationship-led sales. They own "we don't want to build it ourselves" buyers.
- **Specialist-suite zone** — READY! for ePI (NNIT), Docuvera, Datapharm/emc. Narrow functional depth, strong in one region or workflow, limited breadth.

There is a **fourth zone with no credible occupant**:

> **Self-serve enterprise for mid-cap MAHs** — a product a regulatory-ops lead at a company with 20–500 products can procure without a six-figure SOW, stand up inside 30 days, and defend at an EMA inspection. Audit-first, not developer-first.

This is the zone Antigravity can own. It is not occupied by incumbents because:

- **Veeva does not want it** — mid-caps can't justify Vault RIM's floor price, and Veeva's AI Agents are horizontal (document-intelligence first, FHIR-conversion second).
- **Glemser can't reach it** — their managed-service unit economics require human operators in the loop; self-serve would cannibalise their per-document revenue.
- **CROs won't ship it** — labor-arbitrage margin structure is incompatible with a product that reduces labor.
- **READY!/Docuvera don't fit it** — authoring tools, not conversion tools; require customers to adopt component authoring before they see value.

### 1.2 Who the actual buyer is (correcting the marketing brief)

Not developers. Not CTOs. The real buyer in the 60-day window is:

| Buyer | Company profile | Budget authority | What they care about |
|---|---|---|---|
| **Head of Regulatory Operations** | Mid-cap MAH (20–500 products, €100M–€2B revenue) | €50K–€250K/yr, can sign without board approval | EMA deadline, audit defensibility, total-cost-of-ownership vs. Veeva |
| **QA / Validation Lead** | Same companies | Gatekeeper (not buyer but can kill the deal) | Part 11/Annex 11 compliance, CSV documentation, data integrity |
| **Director of Labelling** at CROs | Freyr tier and regional CROs | Per-delivery margin owner | Can they cut their per-document delivery cost 50%+ without the client noticing |

These buyers do not read developer blogs. They attend DIA Europe, read *Regulatory Rapporteur*, and procure through RFPs. The product must ship like enterprise software, even if it's architected like an API.

### 1.3 The 60-day leadership bet

**Win condition in 60 days:**

1. **5 signed design partners** across two segments (3 mid-cap MAHs, 2 regional CROs).
2. **1 production customer** in staging by June 14, 2026.
3. **Validation package** (IQ/OQ/PQ + CSV protocol) that a QA lead can hand to their auditor without modification.
4. **Category language ownership** of two terms: "audit-first FHIR conversion" and "self-serve ePI."
5. **Reference positioning** in at least one analyst note, one DIA Europe session, and one EMA-adjacent community touchpoint (HL7 Vulcan, Gravitate Health).

This is not "overtake Veeva." It is **own the mid-cap segment before Veeva's AI Agents land in August**. Given Veeva takes 6–12 months to implement and mid-caps don't even qualify for the offering, there is a real window.

---

## 2. Enterprise-Readiness Gap Analysis

### 2.1 Current state, truthfully

What exists today (`main.py` + supporting modules, Dockerfile):

- Single stateless endpoint `POST /api/process_stateless` — uploads a DOCX/PDF, returns a 17-field JSON with FHIR bundle and diagnostics.
- CORS `allow_origins=["*"]`, no authentication, no rate limiting.
- `tempfile.TemporaryDirectory()` for inputs — nothing persisted anywhere.
- Exceptions surfaced to client as `str(e)` — leaks internals.
- Audit information (`fix_log`, `validation_log_json`) returned in response only; not persisted.
- No tenant concept, no user concept, no RBAC.
- Validator pipeline runs with `MAX_VALIDATION_ITERATIONS = 1` (Render 30-second budget) and `FIDELITY_TARGET = 99.0`.
- Ghost-header detection implemented in `repair_engine.py` but **not wired into the pipeline** (confirmed P1 in FEATURE_SPEC).
- SPOR codes in `fhir_mapper.py` hardcoded with TODO comment "needs validation against official SPOR list."
- Docker image pre-fetches `hl7.eu.fhir.epil` IG; deployable to Render today.

This is a working prototype. It is not a product an MAH QA lead will accept.

### 2.2 What "enterprise-ready for pharma" actually requires

Seven capability groups, with current fit:

| Capability group | Pharma requirement | Current state | Gap size |
|---|---|---|---|
| **Identity & access** | SSO (SAML/OIDC), RBAC, per-user actions | None | Large |
| **Tenant isolation** | Logical (row-level) or physical (per-tenant DB) separation; optional private VPC | None | Large |
| **Audit trail (Part 11)** | Immutable, timestamped, attributable, exportable, 7+ year retention | In-response-only | Medium |
| **Data integrity (ALCOA+)** | Attributable, Legible, Contemporaneous, Original, Accurate + complete/consistent/enduring/available | Partial (fix log exists; no persistence/signature) | Medium |
| **CSV / validation package** | URS, FS, IQ, OQ, PQ, traceability matrix, validation report | None | Large |
| **Security posture** | TLS everywhere, secrets management, encryption at rest, SOC 2 in progress, DPA, vulnerability scanning, pen test | Basic (Docker + Render TLS only) | Large |
| **Operational maturity** | Uptime SLA, DR/backup, incident response, status page, monitoring | None | Medium |

Two groups (identity and CSV package) are where most 60-day enterprise deals die. Both are addressed head-on in the roadmap below.

### 2.3 What "market-leading product features" requires

Beyond enterprise-readiness, to be the preferred self-serve ePI product a mid-cap MAH picks over Veeva/Glemser, the product must clear these functional bars:

1. **Variation support** — Type IA, IB, II variation packages (not just new MAA submissions). Most ePI work after Q3 is change-management.
2. **Batch processing** — upload 50 documents, get 50 bundles. Async, with progress and resumability.
3. **Reviewer UI** — web interface for QA/Reg-Ops to diff source vs. converted, accept/reject fixes, e-sign the approval. This is the single biggest visible gap vs. Glemser's portal.
4. **Delta / change-set output** — emit a variation package that references the prior submission, not a full re-submission.
5. **Ghost-header repair wired in** — existing `repair_engine.py` capability must hit the main pipeline.
6. **Live SPOR integration** — replace hardcoded codes with validated lookup against EMA's SPOR API.
7. **Semantic fidelity** — complement the `difflib.SequenceMatcher` recall score with section-structure preservation, table-integrity, and cross-reference checks.
8. **Multi-language** — EU mandate touches 24 official languages; initial target: EN + DE + FR + ES + IT covers ~85% of the submission volume.
9. **Roundtrip** — FHIR → DOCX export for reviewer markup.
10. **Connector to Vault Submissions** — "push to Vault" capability, positioning as embeddable rather than competitive.

---

## 3. The 8-Week Roadmap

Four 2-week sprints running two tracks in parallel: **Platform** (identity, persistence, security, validation package) and **Product** (features that show up in demos and win deals).

Sprint cadence: Monday kickoff, Friday demo, rolling retro. Design-partner interviews on Thursdays throughout.

### Sprint 1 — Foundations (Apr 14 → Apr 28)

**Theme:** You cannot sell to a pharma company without identity, persistence, and an audit trail. Build those first.

**Platform track**

- Introduce Postgres (managed, e.g. Neon or AWS RDS) behind SQLAlchemy. Schema: `tenants`, `users`, `api_keys`, `jobs`, `job_events`, `audit_log`, `artifacts`.
- Add API-key authentication as interim layer (before full SSO). Every call carries a tenant; every response carries a `job_id`.
- Persist artifacts to S3-compatible object storage (original upload, generated FHIR bundle, validation log, fidelity report). Content-addressed (SHA-256) keys.
- Replace `main.py`'s CORS `*` with a per-tenant origin allowlist.
- Replace `raise HTTPException(status_code=500, detail=str(e))` with structured error envelope + server-side correlation ID.
- Structured logging (JSON) with request ID, tenant ID, job ID, duration, doc_type, fidelity_score.
- Health endpoint split: `/health` (liveness) and `/ready` (checks DB + object storage + validator).

**Product track**

- **Wire `repair_engine.py` ghost-header repair into the main pipeline**, gated by a feature flag per tenant. This is low-effort, already-written code, and closes an open P1 from the PRD.
- **Live SPOR code validation** — replace `RMS_SPOR_CODES` hardcoding in `fhir_mapper.py` with a nightly-cached lookup against EMA's SPOR API, with fallback to the local dictionary on outage. Log any code mismatch as a structured warning.
- Add request-level idempotency keys so repeated uploads of the same document return the same `job_id`.
- Add upload size and MIME type validation (max 25 MB, DOCX/PDF only, libmagic sniff).

**Enterprise checklist items closed this sprint**

- Encryption in transit (already), encryption at rest (new — RDS + S3 SSE).
- Basic tenant isolation (row-level).
- Audit trail begins accumulating in Postgres.
- Correlation IDs in every log line.
- Structured errors, no internal leakage.

**Exit demo (Fri Apr 24)**

Convert a sample SmPC under two tenant API keys; show that each tenant only sees its own jobs; pull the fix log from the database; show the audit row for a user action; show a 400 on a malformed upload with a correlation ID the customer can quote.

### Sprint 2 — Reviewability (Apr 29 → May 12)

**Theme:** The #1 reason Reg-Ops walks away from a self-serve tool is "I can't prove to QA what was changed and why." Fix that.

**Platform track**

- Immutable `audit_log` table: append-only, hash-chained (each row includes SHA-256 of prior row + current payload), per-tenant retention policy (default 7 years, configurable).
- Per-event signing with a tenant-scoped HMAC key — foundation for Part 11 "attributable."
- Background job queue (RQ or Celery + Redis). Move `process_stateless` work into an async job path. Preserve the synchronous endpoint for API simplicity but introduce `POST /v1/jobs` (async) and `GET /v1/jobs/:id` (poll).
- CI pipeline: GitHub Actions running pytest on PR, Docker build, container scanning (Trivy), dependency audit (pip-audit), secret scanning (gitleaks).

**Product track**

- **Reviewer web UI (MVP)**. Next.js app on top of the API. Screens:
  - Jobs list (tenant-scoped, paginated)
  - Job detail: side-by-side source vs. rendered narrative, toggle-able fix overlay, per-section fidelity bar, per-fix rule annotations
  - Approve / reject / request-change actions (just status changes at this sprint; e-sign comes in Sprint 3)
- **Batch upload** — zip or multi-file upload; returns a single `batch_id` with per-file `job_id`s.
- **Semantic fidelity v1** — structural checks alongside text recall: required sections present, section numbering preserved, table count preserved, cross-reference integrity (all `see section X.Y` targets exist). Emit as a separate score; do not replace existing recall score.

**Enterprise checklist items closed this sprint**

- Immutable, hash-chained audit trail (data-integrity foundations).
- Async job handling for batch workloads.
- Supply-chain hygiene on builds.
- Reviewer UI covers "I want to see what changed before I approve it."

**Exit demo (Fri May 8)**

Upload 12 SmPCs as a batch, open the reviewer, step through the fix log, approve 10, reject 2, show the audit trail. The semantic fidelity card shows "Structure: 100%, Recall: 99.4%, Cross-refs: OK."

### Sprint 3 — GxP Credibility (May 13 → May 26)

**Theme:** The QA lead is now the deciding voice. Hand them the validation package.

**Platform track**

- **21 CFR Part 11 electronic-signature flow** — signed approvals in the reviewer UI with reason codes ("approved", "approved with change", "rejected — non-conformance"), signature meaning displayed, re-authentication for signing ("two-factor within session"), tamper-evident signature blocks in the audit log.
- **SSO (SAML + OIDC)** via a managed identity provider (Auth0, WorkOS, or Ory). Okta, Entra ID, and Google Workspace connector-tested. API keys remain for service-to-service.
- **RBAC** — roles `admin`, `reg_ops`, `qa_reviewer`, `read_only`; policy enforcement middleware per route.
- **Per-tenant data-residency option** — EU region as default (S3 Frankfurt + RDS Frankfurt), with a "pin to EU" flag on tenant creation. Prepared for US pharma's US-region preferences.
- **SOC 2 Type I readiness** — engage auditor; implement control library in Drata/Vanta; start 30-day observation window ending inside Sprint 4.

**Product track**

- **Variation package support (Type IB first)** — accept a prior-submission bundle reference and emit a delta bundle. Critical: this is what Reg-Ops does every day post-submission. The PRD flags it as open-question; we commit here.
- **FHIR → DOCX roundtrip** — regenerate a styled Word document from the validated FHIR bundle so reviewers can redline in their familiar tool. Use `python-docx` with a QRD-aligned template.
- **"Push to Vault Submissions" connector (preview)** — outbound job that takes a validated bundle and produces the artifacts Vault expects, plus a manifest. Positions Antigravity as Vault-complementary (directly addresses the Aug-2026 Veeva AI Agents threat).
- **Multi-language parser path** — extend `doc_parser.py` strategies for DE, FR, ES, IT (recognise localised section headers). EN already handled.

**Enterprise checklist items closed this sprint**

- Part 11 / Annex 11 e-signatures.
- SSO + RBAC.
- EU data residency.
- SOC 2 observation window running.
- DPA and MSA templates drafted and on the website.
- Validation protocol (URS + FS + IQ template) published in a customer-accessible portal.

**Exit demo (Fri May 22)**

QA reviewer logs in via Okta SSO, opens a variation job, applies two fixes, e-signs with reason code, the audit trail shows the cryptographic signature chain and the reason, the bundle auto-pushes to a sandbox Vault Submissions workspace, and the reviewer downloads the roundtripped DOCX for a second-stage QC review.

### Sprint 4 — Market Moment (May 27 → Jun 14)

**Theme:** The window opens. Veeva Copenhagen Summit is May 28–29; DIA Europe is early June; EMA Q3 go-live is end of August. This sprint converts technical readiness into design partners and pipeline.

**Platform track**

- **Finish the CSV package.** OQ and PQ scripts (parametrised against customer data), traceability matrix from URS → requirements → test cases → evidence. Customer-executable: a QA lead can run OQ against their sandbox tenant and produce their own validation report. This is the single asset that closes GxP objections faster than any sales call.
- **Performance hardening.** Raise `MAX_VALIDATION_ITERATIONS` from 1 to 3 in the async path (Render 30-second budget only applies to synchronous; async can run up to 5 minutes). Add concurrency controls and per-tenant quotas.
- **Status page + uptime SLA.** 99.9% target; public status page with historical uptime.
- **Pen test window** — commission a lightweight black-box pen test (1 week, 2 testers). Publish summary letter.

**Product track**

- **Analyst brief.** Short memo (5 pages) to Gartner, Forrester, IDC regulatory tech analysts. Frame: audit-first self-serve category.
- **Two design-partner case studies.** One mid-cap MAH, one CRO. Quantified: time-to-first-bundle, cost-per-bundle, QA effort saved. Published with logo permissions.
- **Public validation benchmark.** 10 known-good SmPCs from open sources (EMA public product information), scored through Antigravity, with the raw audit logs and fidelity reports published. Invite competitors to submit their own scores; commit to updating the leaderboard monthly.
- **Pricing page go-live.** Three tiers: Sandbox (free, 25 conversions/month), Team (€2,400/month, 500 conversions, reviewer UI, SSO), Enterprise (custom, dedicated region, CSV package, DPA, pen-test letter). Mid-cap MAHs can buy Team with a credit card.
- **Vault Submissions connector GA** with a reference architecture document.

**GTM activities this sprint (in parallel with platform/product)**

- Veeva R&D Summit Copenhagen (May 28–29): sponsored session "Embedding FHIR conversion inside Vault RIM workflows."
- DIA Europe (dates confirmed at calendar check): booth or sponsored talk; offer free fidelity-score audits of visitors' own SmPCs.
- HL7 Vulcan biweekly call: present the hash-chained audit log as a contribution idea.
- Gravitate Health forum: offer Antigravity as a reference implementation for their pilot network.

**Enterprise checklist items closed this sprint**

- Full CSV package available for customer execution.
- Pen test complete, summary letter available under NDA.
- SOC 2 Type I report (if observation window closes in time; otherwise Type I letter of engagement).
- Status page live with SLA.
- Pricing published.

**Exit moment (Fri Jun 12)**

Sprint demo becomes a joint design-partner webinar with at least two customers on camera walking through their own validated ePI submissions. Pipeline target entering June 15: 20 qualified opportunities, 5 signed design partners, 1 production customer in staging.

---

## 4. Consolidated Enterprise-Readiness Checklist

Mark-off checklist a procurement team will actually review, mapped to the sprint that closes it.

### 4.1 Security

| Control | Target | Sprint |
|---|---|---|
| TLS 1.2+ everywhere (ingress, intra-service, DB) | Enforced | 1 |
| Encryption at rest (DB + object storage) | AES-256 (AWS/Azure-managed) | 1 |
| Secrets management | Vault or cloud KMS; no secrets in repo | 1 |
| SSO (SAML, OIDC) | Okta, Entra ID, Google | 3 |
| RBAC | 4 roles, route-level policy | 3 |
| Session hardening | Short-lived tokens, refresh rotation, MFA option | 3 |
| API-key hygiene | Scoped, rotatable, revocable, last-used tracking | 1 |
| Dependency scanning | CI-enforced (pip-audit, Trivy) | 2 |
| Secret scanning | Pre-commit + CI (gitleaks) | 2 |
| Vulnerability management | Monthly scan, patch SLO by severity | 3 |
| Pen test | Annual; first run in Sprint 4 | 4 |
| SOC 2 Type I | Report in hand or letter of engagement | 4 |
| GDPR posture | DPA template, DPIA for tenants on request, sub-processor list | 3 |
| Data residency | EU default, US optional | 3 |

### 4.2 Data integrity and Part 11 / Annex 11

| Control | Target | Sprint |
|---|---|---|
| Attributable (every action tied to a user) | Audit log includes user_id, tenant_id, session_id | 1-3 |
| Legible & contemporaneous | Structured JSON, ISO-8601 timestamps, UTC | 1 |
| Original | Source documents preserved in object storage, content-addressed | 1 |
| Accurate | Fidelity score + semantic checks on every run | 2 |
| Complete, consistent, enduring | Hash-chained audit rows; retention policy; export on demand | 2 |
| Electronic signatures | Part 11-compliant flow with reason codes and re-auth | 3 |
| Signature binding | Cryptographic binding of signature to record state | 3 |
| Tamper-evidence | Hash chain verifiable on export | 2 |
| Access control | RBAC enforced at API + UI | 3 |
| Change control | Versioned API, deprecation policy, changelog | 2-4 |

### 4.3 Validation (CSV) package

| Artifact | Status | Sprint |
|---|---|---|
| User Requirements Specification (URS) | Template + customer-editable | 3 |
| Functional Specification (FS) | Derived from FEATURE_SPEC | 3 |
| Installation Qualification (IQ) | Runbook + evidence capture | 3 |
| Operational Qualification (OQ) | Parametrised scripts, customer-executable | 4 |
| Performance Qualification (PQ) | Scenario-based, with customer data | 4 |
| Traceability matrix | URS → FS → DS → test case → evidence | 4 |
| Validation report | Auto-generated from OQ/PQ run | 4 |
| Validation SOP | Customer-branded template | 4 |
| Periodic re-validation plan | Quarterly template | 4 |

### 4.4 Operations

| Control | Target | Sprint |
|---|---|---|
| Uptime SLA | 99.9% business hours, 99.5% 24x7 | 4 |
| RPO | ≤ 1 hour (DB), ≤ 24 hours (object storage) | 2 |
| RTO | ≤ 4 hours | 3 |
| Backup | Daily automated, 30-day retention, quarterly restore test | 2-3 |
| Status page | Public, with incident history | 4 |
| Monitoring | Metrics (Prometheus/Datadog), alerting on SLO breach | 2 |
| Logging | Structured JSON, centralised, searchable, 90-day hot + 1-year cold | 1-2 |
| Incident response runbook | On-call rotation, severity matrix, post-mortem template | 3 |

### 4.5 Commercial / procurement

| Artifact | Sprint |
|---|---|
| Published pricing page (three tiers) | 4 |
| Master Service Agreement (MSA) | 3 |
| Data Processing Agreement (DPA) | 3 |
| Sub-processor list (public) | 3 |
| Insurance certificates (E&O, cyber) | 3 |
| Security questionnaire (SIG Lite, CAIQ) pre-filled | 3 |
| Vendor risk assessment responses bank | 3 |
| Procurement-portal-ready company profile | 4 |

---

## 5. Product Feature Roadmap (explicit scope, sequenced)

Sequencing rationale: every feature must do one of three things — unblock a design-partner signature, close an enterprise procurement objection, or create defensible category language.

| # | Feature | Sprint | Rationale |
|---|---|---|---|
| 1 | Ghost-header repair wired into pipeline | 1 | Closes open P1 in PRD; lifts fidelity on SmPCs with malformed headers (material quality win). |
| 2 | Live SPOR code validation | 1 | PRD-flagged TODO; direct risk to bundles being rejected by EMA validator. |
| 3 | Persisted audit trail (append-only, hash-chained) | 1-2 | Table-stakes for Part 11. |
| 4 | Tenant isolation + API keys | 1 | Unblocks any B2B trial. |
| 5 | Async job queue + batch upload | 2 | Demo-critical: "upload a dossier, not a document." |
| 6 | Reviewer web UI (diff + approve/reject) | 2 | Closes the #1 visible gap vs. Glemser's portal. |
| 7 | Semantic fidelity (structure + table + x-ref) | 2 | Answers QA's "99% of what?" objection from the positioning critique. |
| 8 | E-signature flow with reason codes | 3 | Unblocks GxP-conscious buyers. |
| 9 | SSO + RBAC | 3 | Procurement gate for any pharma > €500M revenue. |
| 10 | Type IB variation support | 3 | Where Reg-Ops actually spends their time; differentiates from vendors that only do MAA. |
| 11 | FHIR → DOCX roundtrip | 3 | Reviewer's familiar tool; reduces switching cost for the customer's internal QC. |
| 12 | Vault Submissions connector (preview) | 3 | Neutralises the Veeva threat by positioning as complement. |
| 13 | Multi-language parser (EN/DE/FR/ES/IT) | 3 | Unblocks EU mid-caps. |
| 14 | Customer-executable CSV package | 4 | Closes the validation gate without custom services. |
| 15 | Public fidelity benchmark | 4 | Category-defining asset; fuels PR. |
| 16 | Pricing page + Sandbox tier | 4 | Converts interest into qualified pipeline with zero sales involvement. |
| 17 | Type II variation support | Post-Jun 14 (P1) | Larger scope, less urgent pre-mandate. |
| 18 | Additional EU languages (NL, PL, SV, DA, FI) | Post-Jun 14 (P1) | Expand coverage. |
| 19 | Full bidirectional Vault RIM sync | Post-Jun 14 (P1) | Deeper integration; requires Veeva partnership conversation. |
| 20 | DADI alignment | Post-Jun 14 (P2) | Watch trend; align when EMA confirms timeline. |

---

## 6. Technical Architecture Target State (end of Sprint 4)

```
                       ┌────────────────────────────┐
                       │   Reviewer Web UI (Next)   │
                       │  SSO • diff • e-sign       │
                       └────────────┬───────────────┘
                                    │ HTTPS
                       ┌────────────▼───────────────┐
                       │   API Gateway / Ingress    │
                       │   (rate limit, WAF)        │
                       └────────────┬───────────────┘
                                    │
  ┌──────────────────┐ ┌────────────▼──────────────┐ ┌──────────────────┐
  │ Identity (SSO)   │ │  FastAPI Service           │ │ Object Storage   │
  │ Okta/Entra/OIDC  ├─┤  /v1/jobs  /v1/batches     ├─┤ S3 (EU/US)       │
  └──────────────────┘ │  /v1/artifacts             │ │ SSE-KMS          │
                       │  /v1/audit  /v1/tenants    │ └──────────────────┘
                       └────────────┬───────────────┘
                                    │
                    ┌───────────────┼──────────────┬────────────────┐
                    │               │              │                │
             ┌──────▼──────┐ ┌──────▼──────┐ ┌─────▼────┐ ┌─────────▼──────────┐
             │  Postgres   │ │  Redis +    │ │  Worker  │ │ FHIR Validator CLI │
             │  tenants/   │ │  RQ/Celery  │ │  pool    │ │ (Java, pre-fetched │
             │  jobs/audit │ │  queue      │ │ (pipeline│ │  hl7.eu.fhir.epil) │
             │  hash-chain │ └──────┬──────┘ │  run)    │ └────────────────────┘
             └─────────────┘        │        └──────────┘
                                    │                           ┌─────────────┐
                                    └──────────────────────────►│ SPOR API    │
                                                                │ (cached)    │
                                                                └─────────────┘

             Observability: structured logs → Loki/CloudWatch → alerting
             CI/CD: GitHub Actions → Trivy + pip-audit → Docker registry → deploy
             Backups: RDS snapshots daily; S3 versioning + lifecycle
             Regions: eu-central-1 default; us-east-1 on demand (tenant flag)
```

Current state (Apr 14) differs from target state by:

- Adds: Reviewer UI, ingress/WAF, identity provider, Postgres, Redis + queue, object storage, worker pool, SPOR cache, CI scanning, observability.
- Keeps: FastAPI core, doc parser strategies, FHIR mapper, two-phase validation pipeline, Docker-packaged Java validator, EMA IG pre-fetch.
- Refactors: `main.py` splits into `api/` (routes + schemas), `services/` (pipeline orchestration), `domain/` (parser, mapper, validator — unchanged logic, injected dependencies).

---

## 7. Team and Resourcing

Minimum team to execute in 8 weeks:

| Role | FTE | Scope |
|---|---|---|
| Tech lead / backend | 1.0 | Core API, persistence, auth, audit, pipeline integration |
| Backend engineer | 1.0 | Worker, batch, connectors, SPOR integration |
| Frontend engineer | 0.8 | Reviewer UI |
| QA / validation engineer | 0.8 | CSV package, OQ/PQ scripts, fidelity benchmarks |
| Product / reg-ops SME | 0.5 | Customer calls, requirements, design-partner delivery |
| Designer | 0.3 | Reviewer UI, pricing page, CSV artifact templates |
| Growth / content | 0.5 | Pricing page, analyst brief, case studies, DIA/Veeva event ops |

Total: ~5.0 FTE. If constrained below this, the sequence is: cut multi-language (Sprint 3), cut Vault connector (Sprint 3), cut pen test (Sprint 4, defer to Q3). Do not cut audit trail, SSO, reviewer UI, or CSV package — each is a direct procurement blocker.

External dependencies to line up this week:

- SOC 2 / compliance-as-code vendor (Drata, Vanta, or Secureframe) — contract by Fri Apr 18.
- Pen-test vendor — scope agreed by end of Sprint 2.
- Managed identity provider (Auth0, WorkOS, Ory) — vendor selected by Fri Apr 18.
- Legal review of MSA + DPA templates — engage counsel this week.
- Design-partner candidates — target list of 15 mid-cap MAHs and 5 regional CROs drafted by Fri Apr 18; first calls in week 2.

---

## 8. Success Metrics

Leading indicators tracked weekly:

| Metric | Baseline (Apr 14) | Target (Jun 14) |
|---|---|---|
| Design-partner intros completed | 0 | 25 |
| Design partners signed (LOI) | 0 | 5 |
| Production customers in staging | 0 | 1 |
| Sandbox signups | 0 | 100 |
| Qualified opportunities (€50K+ annual) | 0 | 20 |
| DPA/MSA reviewed with counsel | No | Yes |
| SOC 2 Type I letter of engagement | No | Yes |
| Pen test status | Not scoped | Report delivered |
| CSV package completeness (URS/FS/IQ/OQ/PQ/TM) | 0/6 | 6/6 |
| Validation benchmark docs published | 0 | 10 |
| Reviewer UI: time from upload to signed approval (p50) | N/A | < 10 minutes |
| SPOR lookup coverage (codes resolved against live API) | 0% | 100% of SmPC mappings |

Lagging indicators tracked by Jul 14 (one month post-window):

- Paid conversions from Sandbox → Team tier
- First-year ARR signed
- Category terms ("audit-first FHIR conversion", "self-serve ePI") appearing in at least one analyst note or major industry publication

---

## 9. Risk Register (roadmap-scoped)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Sprint 3 CSV package underestimated | High | Large | Start templates in Sprint 2; engage a GxP consultant on retainer for review. |
| SOC 2 Type I not achievable in 8 weeks | High | Medium | Offer "letter of engagement + control implementation evidence" as interim; Type I report by mid-Jul. |
| Veeva ships AI-Agent DOCX→FHIR in Aug 2026 GA | Medium | Large | Vault-complementary positioning and Sprint 3 connector ship *before* their GA; capture reference architecture wins regardless of their scope. |
| Reviewer UI design takes longer than 2 weeks | Medium | Medium | Start with accept/reject-only MVP; defer inline annotation to Sprint 3 if needed. |
| EMA SPOR API rate limiting / downtime | Medium | Medium | Local cache with 24-hour TTL + fallback to hardcoded dictionary; log mismatches as warnings. |
| Design-partner contract cycles exceed 8 weeks | High | Medium | Use LOI + paid pilot with 30-day opt-out (lower legal friction than full MSA); MSA conversions target Q3. |
| Pen test surfaces a blocker finding | Medium | Large | Schedule pen test week 6 of 8 to leave a window for remediation before Jun 14. |
| The fidelity score is attacked as insufficient for GxP | Medium | Large | Ship semantic fidelity v1 in Sprint 2; frame score publicly as "one signal of many" not "the only signal"; tie every number to the full audit log. |

---

## 10. Week-by-Week Calendar

| Week | Sprint | Platform focus | Product focus | GTM milestone |
|---|---|---|---|---|
| W1: Apr 14–20 | S1 | Postgres, API keys, object storage | Ghost-header wire-in | Design-partner target list; vendor selections closed |
| W2: Apr 21–27 | S1 | CORS tightening, error envelopes, audit log table | SPOR integration, idempotency | First 10 design-partner intro calls |
| W3: Apr 28–May 4 | S2 | Hash-chained audit, async queue, CI scanning | Reviewer UI skeleton, batch upload | Next 10 intro calls; 3 LOIs targeted |
| W4: May 5–11 | S2 | Monitoring + SLO instrumentation | Reviewer UI diff + approve, semantic fidelity v1 | Analyst brief draft circulated |
| W5: May 12–18 | S3 | SSO + RBAC; EU residency | Type IB variation; e-signatures; DOCX roundtrip | Veeva Copenhagen agenda confirmed; DIA Europe booth confirmed |
| W6: May 19–25 | S3 | SOC 2 observation window opens; DPA/MSA live | Vault connector preview; multi-language parser | 5 LOIs signed target; analyst calls week |
| W7: May 26–Jun 1 | S4 | Pen test week | OQ/PQ scripts; pricing page design | Veeva Copenhagen (May 28–29): sponsored session |
| W8: Jun 2–14 | S4 | Status page, SLA, remediation from pen test | CSV package GA; fidelity benchmark publish; pricing page live | DIA Europe; joint design-partner webinar; pipeline review |

---

## 11. Immediate Decisions (this week)

To keep the 8-week window intact, the following must be decided by Friday Apr 18:

1. Identity provider choice (Auth0 / WorkOS / Ory).
2. Compliance-as-code vendor (Drata / Vanta / Secureframe).
3. Cloud choice and region pinning (AWS eu-central-1 vs. Azure West Europe — drives procurement behaviour in EU pharma; AWS is default assumption).
4. Pen-test vendor shortlist.
5. Legal counsel for MSA/DPA review.
6. Hiring or contracting for the frontend engineer and QA/validation engineer if not on team today.
7. Final team headcount and budget sign-off.

Every day of slippage on these six decisions compresses Sprint 4, which is the sprint that closes deals.

---

*End of roadmap.*
