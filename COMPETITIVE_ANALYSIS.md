# Competitive Analysis: ePI Processing Backend (Antigravity ePI Conversion Engine)

**Date:** 2026-04-14
**Subject product:** FastAPI-based stateless document → FHIR R4 ePI (EMA `hl7.eu.fhir.epil`) conversion engine, v2.0.0
**Prepared for:** Product strategy and GTM positioning decisions ahead of EMA's Q3/Q4 2026 phased go-live for Centrally Authorised Products

---

## Executive Summary

The EMA's phased ePI go-live begins Q3 2026 (voluntary, vaccines, ATC J07) and Q4 2026 (oncology, ATC L01/L04), with a wider rollout in 2027. The AI-in-regulatory-affairs TAM is estimated at **USD 1.83–2.11B in 2026**, growing at **~22% CAGR** toward USD 4.78B by 2030. The subject product enters a market that is (1) **not yet consolidated** around a dominant ePI conversion tool, (2) **dominated on the suite side** by Veeva Vault RIM and IQVIA with months-long implementation cycles, and (3) **thinly served on the point-solution side** by Glemser, MT-G, i4i, READY! for ePI, and Datapharm — most of which are either consulting-led or embedded inside a broader SCA platform.

**The subject product's strategic opening is the "developer-first, stateless, sub-30-second API" position — essentially no incumbent owns it.** The dominant competitive risk is Veeva adding a native DOCX→FHIR converter inside Vault RIM (their AI Agents release is scheduled for August 2026).

**Win/loss hypotheses:** Wins on speed + API-native integration + transparent fidelity scoring; losses on brand trust, end-to-end workflow (CCMS + RIM + submission gateway), and live SPOR terminology binding.

---

## 1. Competitive Landscape

### 1.1 Direct Competitors (DOCX/PDF → FHIR ePI conversion, same user, same problem)

| # | Vendor | Product | Delivery Model | Differentiator |
|---|--------|---------|----------------|----------------|
| D1 | **Glemser** | ComplianceAuthor ePI FHIR conversion | Managed service, secure portal, 24–48h SLA | NLP + GenAI; scales to thousands of conversions; "up and running in <5 days" |
| D2 | **MT-G** | FHIR-compliant ePI transformation | Consulting + language service (human-in-loop) | Translation + structured content combined; multilingual; EMA UAT participant (June 2025) |
| D3 | **i4i** | Structured content platform with FHIR ePI publishing | On-prem/cloud platform | Multi-jurisdiction (SPL, Health Canada XML PM, FHIR ePI Jordan + EMA); central repo with reuse |
| D4 | **READY! for ePI (NNIT)** | DiCE authoring + READY! ePI FHIR Gateway | SaaS authoring + submission gateway | Purpose-built for ePI end-to-end; gateway-to-EMA submission |
| D5 | **Datapharm (emc)** | SmPC/PIL → FHIR conversion tied to emc publishing | Managed, UK-focused | Gravitate Health partner; emc.uk consumer-display surface |
| D6 | **Appnovation** | Digital ePI with FHIR (custom consulting) | Bespoke engagements | Enterprise consultancy; UX/portal build alongside conversion |

### 1.2 Indirect Competitors (same problem, different approach — usually as a module inside a bigger suite)

| # | Vendor | Product | Approach |
|---|--------|---------|----------|
| I1 | **Veeva Vault RIM** | Submissions + FHIR message transmission (PMS) | Suite with RIM + CrossLink + 26R1 FHIR messaging; **AI Agents for RIM** GA Aug 2026 (auto-tag, labeling paragraphs, missing-content detection) |
| I2 | **IQVIA RIM Smart Content Management** | Labeling + RIM module | Suite with deep reg-ops and labeling ties; IQVIA–Veeva partnership (2025) |
| I3 | **Docuvera** | AI-powered Structured Content Authoring (SCA) | Component-based authoring; aligned to eCTD 4.0, ePI, DADI, FHIR |
| I4 | **LORENZ docuBridge** | eCTD publishing/validation | Dossier-level publishing; adjacent to ePI via same submission surface |
| I5 | **EXTEDO** (eCTDmanager / EXTEDOpulse) | eCTD + RIM suite | Strong Module-1 template library US/EU/JP |
| I6 | **PTC Arbortext / OpenText / Vasont** | Generic SCA/CCMS | Legacy structured-authoring; retrofitted for life sciences |
| I7 | **GLAMS ePI** | ePI module | Niche ePI-authoring entrant |

### 1.3 Substitute Solutions

| # | Substitute | Who uses it today | Why |
|---|------------|-------------------|-----|
| S1 | **Manual conversion by internal reg-ops teams** | Most MAHs pre-mandate | "Non-consumption" — wait-and-see posture; ~10 hours/document reported |
| S2 | **CRO outsourcing** (Freyr, ProductLife, Parexel, Accenture Life Sciences) | Mid-to-large MAHs without in-house FHIR skill | Full-service: reg-ops + publishing + submission; typical CRO savings ~30% vs. in-house |
| S3 | **DIY with HAPI FHIR + `validator_cli.jar`** | Tech-forward in-house teams | Apache 2.0 open-source; the subject product itself uses this stack under the hood |
| S4 | **Do nothing / delay** | MAHs outside vaccine + oncology first-wave | Not yet compulsory; purely voluntary for CAPs through 2026 |

### 1.4 Adjacent / Potential Competitors

- **Veeva AI Agents (Aug 2026 GA)** — closest disruption risk; could absorb point-solution conversion entirely inside Vault RIM.
- **Hyperscalers** — AWS HealthLake, Azure Health Data Services, Google Cloud Healthcare API all speak FHIR natively and could add ePI profile packs.
- **Datapharm / Gravitate Health ecosystem** — if Gravitate's EU-funded stack matures into reference implementations, it could become free baseline infrastructure.
- **LLM-native reg-tech startups** — any new entrant that ships a GenAI pipeline against `hl7.eu.fhir.epil` this year; Glemser's ComplianceAuthor is already in this zone.

---

## 2. Landscape Map

**Primary axes (what reveals strategic separation in this market):**

1. **X: Breadth** — Point solution (FHIR conversion only) ↔ Suite (RIM + SCA + submission + publishing)
2. **Y: Delivery model** — Self-serve API ↔ Managed service/consulting

```
                                  SELF-SERVE API / TOOL
                                          │
                              ┌───────────┼───────────────────────┐
                              │           │                       │
                              │   ⭐ Antigravity ePI Backend       │
                              │      (subject product)            │   ← open position:
                              │                                   │     "stateless API,
                              │                                   │      fast, transparent"
                              │   HAPI + validator_cli.jar (S3)   │
                              │   (DIY)                           │
                              │                                   │
                              │                    READY! for ePI │   Veeva Vault RIM (I1)
                              │                    (D4)           │   ◆ AI Agents Aug 2026
                              │                                   │   IQVIA (I2)
                              │                                   │   Docuvera (I3)
                              │                                   │   LORENZ (I4) / EXTEDO (I5)
                              │                                   │
 POINT SOLUTION ──────────────┼───────────────────────────────────┼──── BROAD SUITE
                              │                                   │
                              │   Glemser ComplianceAuthor (D1)   │   Freyr (S2) / ProductLife /
                              │   Datapharm (D5)                  │   Accenture / Parexel (CRO)
                              │   MT-G (D2)                       │   i4i (D3) (publisher+SCA)
                              │   Appnovation (D6)                │
                              │                                   │
                              │   GLAMS (I7)                      │
                              │                                   │
                              └───────────────────────────────────┘
                                          │
                                MANAGED SERVICE / CONSULTING
```

**What the map reveals.** The **top-left quadrant ("self-serve API point-solution")** is the subject product's strategic white space. The only other inhabitant is open-source DIY — which is technical-debt-heavy and requires an in-house FHIR expert. The top-right (self-serve suites) is Veeva + IQVIA + Docuvera territory — deep moats, long implementation cycles (6–12 months), six-figure annual contracts. The bottom rows are managed-service plays — slower, more expensive per document, but trusted by reg-ops buyers who prefer accountability over tooling.

---

## 3. Feature Comparison Matrix

Rating scale: **Strong** (market-leading), **Adequate** (functional), **Weak** (limited gaps), **Absent** (not available).

| Capability Area / Feature | Antigravity ePI Backend | Glemser (D1) | MT-G (D2) | i4i (D3) | READY! (D4) | Veeva Vault RIM (I1) | Docuvera (I3) | Freyr CRO (S2) | DIY HAPI (S3) |
|---|---|---|---|---|---|---|---|---|---|
| **Ingestion** | | | | | | | | | |
| DOCX parsing (tables, styles, images) | Strong | Strong | Strong | Strong | Strong | Adequate | Strong | Strong | Absent |
| PDF parsing | Adequate | Strong | Strong | Adequate | Adequate | Adequate | Adequate | Strong | Absent |
| Auto-detect document type (SmPC/PIL/Labelling) | Strong | Adequate | Adequate | Adequate | Strong | Absent | Adequate | Strong | Absent |
| **Mapping & profile conformance** | | | | | | | | | |
| `hl7.eu.fhir.epil` IG conformance | Strong | Strong | Strong | Strong | Strong | Adequate | Adequate | Strong | Weak (DIY) |
| SPOR code mapping | Adequate (partial, unverified) | Strong | Strong | Strong | Strong | Strong | Adequate | Strong | Absent |
| Multi-jurisdiction (SPL, XML PM, FHIR ePI) | Absent (EMA only) | Strong | Adequate | Strong | Adequate | Strong | Adequate | Strong | Absent |
| **Validation & auto-fix** | | | | | | | | | |
| HL7 Java CLI validation | Strong | Strong | Strong | Strong | Strong | Strong | Adequate | Strong | Strong |
| Auto-fix XHTML hygiene (namespace, self-closing, entities, unclosed tags, table borders) | Strong (10 fix rules) | Adequate | Adequate | Adequate | Adequate | Weak | Adequate | Adequate | Absent |
| Structured fix audit log (per-rule, per-iteration) | Strong | Adequate | Adequate | Adequate | Adequate | Weak | Adequate | Weak | Absent |
| Live SPOR terminology validation | Weak (filtered as config issue) | Adequate | Adequate | Strong | Strong | Strong | Adequate | Strong | Absent |
| **Fidelity / QA** | | | | | | | | | |
| Recall-based fidelity score (0–100) | **Strong (unique)** | Absent | Absent | Absent | Absent | Absent | Absent | Absent | Absent |
| Visual source-vs-output diff | Strong | Adequate | Adequate | Adequate | Adequate | Adequate | Adequate | Weak | Absent |
| Iterative fidelity improvement loop (target 99%) | **Strong (unique)** | Adequate | Adequate | Weak | Weak | Weak | Weak | Weak | Absent |
| **Integration / developer surface** | | | | | | | | | |
| REST API, single stateless endpoint | Strong | Weak (portal upload) | Absent (consulting) | Weak | Adequate | Adequate (SOAP/REST mix) | Adequate | Absent | N/A |
| SDK / OpenAPI docs | Adequate (FastAPI auto-docs) | Absent | Absent | Adequate | Adequate | Strong | Adequate | Absent | Strong |
| Dockerized deployment | Strong | Absent (hosted only) | Absent | Adequate | Adequate | Absent (SaaS only) | Absent | N/A | Strong |
| Webhooks / async background jobs | Absent | Strong | N/A | Adequate | Adequate | Strong | Adequate | N/A | Absent |
| **Latency** | | | | | | | | | |
| Single-document turnaround | **<30s** | 24–48h | 1–5 days | Minutes–hours | Minutes | Minutes | Minutes | 3–5 days | Self-run |
| **Workflow / suite depth** | | | | | | | | | |
| Structured content authoring (reusable components) | Absent | Adequate | Adequate | Strong | Strong | Strong | Strong | Adequate | Absent |
| Translation / multilingual management | Absent | Adequate | **Strong** | Strong | Adequate | Strong | Adequate | Strong | Absent |
| Submission gateway to EMA | Absent | Adequate | Weak | Adequate | **Strong** | Strong | Weak | Strong | Absent |
| Dossier-level publishing (eCTD) | Absent | Adequate | Absent | Adequate | Adequate | Strong | Adequate | Strong | Absent |
| RIM / regulatory information management | Absent | Absent | Absent | Adequate | Absent | **Strong** | Absent | Strong | Absent |
| **Enterprise readiness** | | | | | | | | | |
| Auth, RBAC, audit, SOC2 | **Absent (CORS `*`)** | Strong | Strong | Strong | Strong | Strong | Strong | Strong | N/A |
| Multi-tenant isolation | Absent | Strong | N/A | Strong | Strong | Strong | Strong | Strong | N/A |
| GxP / 21 CFR Part 11 validation package | Absent | Strong | Adequate | Strong | Strong | Strong | Strong | Strong | Absent |
| **Commercial** | | | | | | | | | |
| Self-serve pricing | Unknown (dev-stage) | Per-document fixed fee | Quote-based | Enterprise license | Enterprise license | Enterprise license (100k+/yr) | Enterprise license | T&M consulting | Free (OSS) |
| Free trial / sandbox | Possible (stateless API) | Portal demo | Consulting demo | Demo | Demo | Limited | Demo | N/A | Free |

### Key observations

1. **The subject product is uniquely strong on three axes:** (a) recall-based fidelity scoring with visual diff, (b) an iterative fidelity-improvement loop with a transparent fix audit log, and (c) sub-30-second stateless REST API latency. **No competitor in this matrix has all three.**
2. **The subject product is materially weak on:** authentication/RBAC, multi-tenant isolation, GxP validation package, multi-jurisdiction profiles, submission gateway to EMA, and the surrounding SCA/translation/RIM workflow. These are table-stakes for enterprise MAHs.
3. **Veeva's August 2026 AI Agents release is the single largest competitive risk** — if those agents land with even "Adequate" DOCX→FHIR conversion, the subject product loses access to Veeva-customer MAHs (the majority of top-50 pharma) without ever being evaluated.

---

## 4. Positioning Analysis

### 4.1 Incumbent positioning

- **Veeva Vault RIM (I1):** "The RIM platform of record for life sciences." Category = RIM suite; differentiator = breadth + data model maturity; proof = top-20-pharma customer logos.
- **Glemser (D1):** "On-demand FHIR conversion in 24–48 hours." Category = managed conversion service; differentiator = speed + GenAI/NLP; proof = ComplianceAuthor AI + hundreds-to-thousands of conversions.
- **MT-G (D2):** "Language + structured content for regulated medicine." Category = pharma language service; differentiator = translation expertise bundled with FHIR transformation; proof = EMA UAT participation (June 2025).
- **i4i (D3):** "The structured content company." Category = global labeling SCA platform; differentiator = multi-jurisdiction (SPL + XML PM + FHIR ePI); proof = jurisdictional breadth.
- **READY! for ePI (D4):** "Purpose-built for ePI, with submission gateway." Category = dedicated ePI authoring + transmission; differentiator = end-to-end from draft to EMA.
- **Docuvera (I3):** "AI-powered modular structured content authoring." Category = next-gen SCA; differentiator = component reuse + AI drafting.
- **Datapharm (D5):** "Gravitate Health's operational arm in the EU ePI network." Category = ePI display + conversion; differentiator = emc distribution and ecosystem partnerships.
- **Freyr + CROs (S2):** "End-to-end regulatory operations, outsourced." Category = reg-ops services; differentiator = headcount + cost savings vs. in-house.

### 4.2 Unclaimed and crowded positions

**Unclaimed:**
- **"Developer-first, API-first, minutes-not-days, transparent fidelity scoring"** — nobody owns this. The closest is DIY HAPI, which is not a product. Glemser is managed-service, Veeva is a suite, i4i is enterprise platform.
- **"Embeddable FHIR conversion inside existing RIM/CCMS workflows"** — no vendor has publicly positioned as the Stripe/Twilio of ePI conversion.
- **"Audit-transparent AI: every fix logged with rule ID, location, before/after"** — the GxP-sensitive buyer cares about explainability; nobody leads with this.

**Crowded:**
- "AI-powered" (Docuvera, Glemser, Veeva, nearly every new entrant).
- "End-to-end ePI" (READY! for ePI, i4i, Veeva, Freyr all claim this).
- "FHIR-compliant" (table stakes in 2026).

### 4.3 Recommended positioning statement

> **For regulatory-operations engineering teams at MAHs and reg-tech integrators** who need to convert SmPC/PIL/Labelling documents into EMA-conformant FHIR ePI bundles at scale without adopting a full RIM suite, **Antigravity ePI Backend** is a **stateless FHIR conversion API** that **returns a validated, fidelity-scored FHIR Bundle in under 30 seconds per document, with a transparent per-rule fix audit log**. **Unlike Veeva Vault RIM or i4i**, it does not require a 6–12 month implementation or a suite commitment. **Unlike Glemser or MT-G**, it runs as a self-serve API rather than a managed-service portal, and returns results in seconds rather than 1–2 business days.

---

## 5. Win/Loss Hypotheses

Because the product is pre-launch, these are forward-looking hypotheses to validate via design-partner interviews in Phase A.

### 5.1 Expected wins — why a prospect picks the subject product

| # | Win scenario | Root cause |
|---|---|---|
| W1 | "We need to ship a first ePI-ready submission by Q4 2026 and cannot wait on a Vault RIM implementation." | Speed-to-value: weeks not quarters |
| W2 | "Our platform team already owns a Supabase/Next.js reg-ops UI; we just need the conversion engine." | API-native integration |
| W3 | "We want to rerun conversions on every SmPC edit and see the fidelity score drop before QA does." | Transparent scoring + idempotent fixes |
| W4 | "Our QA auditor insists on a line-by-line record of every automated transformation." | Fix audit log (rule ID, location, before/after) |
| W5 | "We're a mid-cap biotech without dedicated FHIR staff; DIY is off the table and Veeva is too expensive." | Pricing + no-expertise-required |

### 5.2 Expected losses — why a prospect picks someone else

| # | Loss scenario | Root cause | Mitigation |
|---|---|---|---|
| L1 | "We already run Veeva Vault RIM; we'll wait for Veeva's AI Agents in August 2026." | Incumbent advantage / platform gravity | Position as complementary embedding inside Vault; offer zero-lift Veeva connector |
| L2 | "Our legal team won't approve open CORS and no SOC2." | Enterprise readiness gap (P2 in spec) | Ship auth + RBAC + SOC2 roadmap on day one |
| L3 | "We need SPL for FDA, Health Canada XML PM, and FHIR ePI all from one doc." | Multi-jurisdiction gap | Prioritize i4i-parity jurisdictional coverage in v2 |
| L4 | "Our reg-ops team wants one vendor accountable for the full submission, not just conversion." | Trust + accountability | Partner with a CRO (e.g. Freyr) for co-sell of managed wrapper around the API |
| L5 | "We want a human-in-loop editor so reviewers can accept/reject individual fixes." | Workflow gap | Add P1 patch API + UI reference implementation |
| L6 | "Glemser quoted us $X per document at volume and includes translation QA." | Pricing opacity + managed-service bundling | Publish per-call pricing; offer translation partner |

### 5.3 Segmented competitive win-rate targets (first 12 months)

- **Mid-cap MAHs (50–500 products):** Target 30% win rate vs. Glemser, 15% vs. Veeva — these buyers are most speed-sensitive and pricing-sensitive.
- **Reg-tech integrators / RIM alternatives:** Target 50% win rate — they need an OEMable API, not a suite.
- **Large pharma (top 20):** Target <5% direct win; instead pursue embedded partnership deals via a CRO or Supabase-frontend partner.

---

## 6. Market Trend Analysis

### Trend 1 — EMA ePI phased go-live accelerating
- **What:** Voluntary Q3 2026 (vaccines, ATC J07) → Q4 2026 (oncology, ATC L01/L04) → expanded therapeutic areas 2027+.
- **Why now:** EMA published the ePI roadmap in March 2026; Network Data Board adopted the common standard in 2021 and the `hl7.eu.fhir.epil` IG v1.0.0 is now frozen.
- **Who's affected:** All MAHs with centrally authorised products in Europe first; nationally authorised products to follow.
- **Timeline:** Peak urgency 2026 Q3 – 2027 Q2.
- **Implication for us:** **Ship v1 by end of Q2 2026 or lose first-mover advantage.** Phase A launch is on the critical path.
- **Competitor response:** Glemser is actively onboarding; Veeva 26R1 (April 2026) added FHIR message transmission; READY! for ePI is positioning gateway-first.
- **Strategic stance:** **Lead.** This is the window.

### Trend 2 — GenAI / LLM adoption inside reg-tech
- **What:** AI-in-regulatory-affairs TAM USD 1.83–2.11B in 2026, 22.7% CAGR; Veeva AI Agents for RIM GA August 2026 (auto-tagging, labeling paragraphs, missing-content detection).
- **Why now:** Foundation-model reasoning has crossed the threshold for structured-document understanding; regulators (EMA, FDA) have begun issuing AI-use guidance.
- **Who's affected:** Every regulatory function — submissions, labeling, pharmacovigilance.
- **Timeline:** Production adoption 2026–2027; policy-validated adoption 2027–2028.
- **Implication for us:** The subject product's current pipeline is largely rule-based (regex + XHTML fixers + difflib scoring). To remain differentiated on quality beyond 2026 Q4, add LLM-assisted fidelity repair and section-boundary detection as v2 capabilities — while preserving the rule-based path for GxP-auditability.
- **Competitor response:** Glemser ComplianceAuthor, Docuvera, Veeva all leading with "AI-powered" messaging.
- **Strategic stance:** **Fast follow.** Do not out-market Veeva on AI; instead, differentiate on explainable AI + deterministic rule traces.

### Trend 3 — Structured content authoring (SCA) convergence with FHIR
- **What:** i4i, Docuvera, and Veeva are converging on a "author-once, publish-many" paradigm where ePI is one of several outputs from a shared component repo.
- **Why now:** eCTD 4.0 (Japan mandating April 2026, EMA accepting since December 2025), IDMP mandates (June + December 2026), and ePI are all arriving simultaneously and share data primitives.
- **Timeline:** 3–5 years for full SCA/FHIR convergence in top-50 pharma.
- **Implication for us:** The subject product is **downstream of SCA** — customers who adopt component-based authoring will eventually not need document-level conversion at all. We have a 2–4 year window where DOCX is still the source of truth.
- **Competitor response:** All suite vendors are investing heavily here.
- **Strategic stance:** **Monitor + build SCA bridges.** Do not compete on SCA breadth; instead, offer an adapter from a component repo (e.g. Docuvera export) directly to our FHIR pipeline.

### Trend 4 — Outsourcing vs. insourcing economics
- **What:** In-house conversion averages ~10 hours per document; CROs report ~30% savings; vendors like Glemser publish 1–2 day SLAs.
- **Why now:** MAHs faced with volume-at-once from the ePI mandate lack the headcount to insource at scale.
- **Timeline:** Peak outsourcing demand 2026–2027.
- **Implication for us:** There is a product-market fit for **"API for the CRO itself."** CROs want to lower cost-per-conversion and drive margin. Selling to Freyr / ProductLife / Accenture Life Sciences as a backend is a viable wedge — they become distributors, not competitors.
- **Strategic stance:** **Lead on CRO-OEM partnerships.**

### Trend 5 — Regulatory AI governance scrutiny
- **What:** EMA and FDA both issued AI-in-regulatory-submissions guidance in 2024–2025 emphasising explainability and traceability.
- **Implication for us:** The subject product's existing **per-rule, per-iteration fix audit log** is already a defensible asset. Package it as a "GxP-ready transformation ledger."
- **Strategic stance:** **Lead on auditability messaging.**

---

## 7. Strategic Implications

### 7.1 Three positioning plays, ranked

1. **Primary: "The Stripe of ePI conversion"** — self-serve, API-first, per-call pricing, developer-first documentation, instant sandbox. Targets reg-tech integrators, CROs, and engineering-led mid-cap MAHs.
2. **Secondary: "GxP-ready transformation ledger"** — lead with the fix audit log, fidelity score, and visual diff as the proof that automated conversion is audit-defensible. Targets QA and compliance buyers.
3. **Tertiary: "Veeva-adjacent, Veeva-complementary"** — explicitly position as embedding inside Vault RIM workflows (via Veeva's CrossLink and REST APIs) rather than replacing them. Neutralise Veeva incumbent risk.

### 7.2 Investment recommendations (next 2 quarters)

| Priority | Investment | Rationale |
|---|---|---|
| **P0** | Close the enterprise-readiness gap (auth, RBAC, SOC2 roadmap, multi-tenant) | L2 loss scenario blocks every enterprise deal |
| **P0** | Verify and fully wire SPOR section codes in `fhir_mapper.SMPC_SECTION_MAPPING` | Spec open question #2 — currently a submission-rejection risk |
| **P0** | Ship OpenAPI docs + sandbox + per-call pricing before Veeva AI Agents (Aug 2026) | Capture the "stateless API" position before the incumbent consumes it |
| **P1** | CRO OEM partnership pilot with Freyr or ProductLife | Turn the largest substitute (CRO services) into a distribution channel |
| **P1** | Multi-jurisdiction profile pluggability (FHIR ePI Jordan, FDA SPL scaffolding) | Pre-empt i4i's multi-jurisdiction lead |
| **P1** | Submission gateway connector (EMA PMS / IDMP submission) | Close the L4 loss ("we want one vendor accountable end-to-end") |
| **P2** | LLM-assisted fidelity-fix strategy (kept separable from rule-based path) | Parity with Veeva AI Agents without sacrificing audit log |
| **P2** | Human-in-loop patch API + reference editor UI | Close L5; unlocks design-partner deals requiring manual override |

### 7.3 Defensive watchlist (monitor weekly)

- **Veeva 26R2 release notes and AI Agents Aug 2026 launch materials** — specifically any DOCX→FHIR demo.
- **Glemser ComplianceAuthor** API/pricing public surface — they are the closest functional analog; any move to self-serve API parity is a direct threat.
- **EMA ePI IG versioning** (`hl7.eu.fhir.epil`) — rebuild Docker cache on every bump.
- **HL7 Vulcan / Gravitate Health** release cadence — could become free reference implementation that commoditises our wedge.
- **Funding announcements** for any AI-native reg-tech startup targeting ePI specifically.

### 7.4 Open questions to resolve with design partners

1. Is the sub-30-second latency materially better than 24–48-hour batch conversion for our target buyer, or is it a "nice to have"?
2. Does the fix audit log alone satisfy GxP audit expectations, or is a separate validation package required?
3. What would it cost to be an OEM partner of a CRO, and how does that constrain direct-sale pricing?
4. Which is the easier first beachhead — reg-tech integrators or mid-cap MAHs?
5. Do Veeva customers have any contractual flexibility to embed a non-Veeva conversion API, or does their Vault commitment preclude it?

---

*End of analysis.*

## Sources

- [EMA Electronic product information (ePI)](https://www.ema.europa.eu/en/human-regulatory-overview/marketing-authorisation/product-information-requirements/electronic-product-information-epi)
- [European Medicines Regulatory Network ePI Implementation Guide v1.0.0](https://epi.ema.europa.eu/fhirig/)
- [EMA adopts common EU standard for ePI (news)](https://www.ema.europa.eu/en/news/european-medicines-regulatory-network-adopts-eu-common-standard-electronic-product-information)
- [EU-ePI-common-standard (EMA GitHub)](https://github.com/EuropeanMedicinesAgency/EU-ePI-common-standard)
- [ForgeStop — ePI Roadmap 2026 compliance checklist](https://www.forgestop.com/blog/epi-roadmap-2026-pharma-compliance-checklist)
- [PharmDedict — EMA strategic roadmap for ePI](https://pharmdedict.com/ectronic-product-information-epi/)
- [Pharmavibes — The EU ePI initiative 2026](https://www.pharmavibes.co.uk/2026/03/31/the-evolution-of-epi-in-the-european-union/)
- [European Pharmaceutical Review — EU adopts ePI standard](https://www.europeanpharmaceuticalreview.com/news/168810/eu-adopts-electronic-product-information-standard-for-medicines/)
- [Glemser — On-demand HL7 FHIR conversion services](https://glemser.com/on-demand-hl7-fhir-conversion-services/)
- [Glemser — Preparing for ePI FHIR conversions](https://glemser.com/blog/preparing-for-epi-fhir-conversions/)
- [Glemser — Mastering the magnitude of ePI FHIR conversions](https://glemser.com/blog/mastering-the-magnitude-of-epi-fhir-conversions/)
- [MT-G — FHIR-compliant electronic product information](https://www.mt-g.com/en/language-solutions/we-empower-you-to-reach-the-world/electronic-product-information)
- [i4i — the structured content company](https://www.i4i.com/)
- [READY! for ePI](https://www.ready4epi.com/)
- [READY! for ePI features](https://www.ready4epi.com/ready-for-epi-features/)
- [Datapharm — ePI and patient information leaflets](https://www.datapharm.com/resource-hub/electronic-product-information-patient-information-leaflets-epi-regulatory-affairs/)
- [Datapharm — FHIR 101 for pharma](https://www.datapharm.com/resource-hub/fhir-101-pharmas-guide-to-the-emerging-standard-in-healthcare-information/)
- [Gravitate Health — FHIR IG for ePI published](https://www.gravitatehealth.eu/fhir-implementation-guide-for-epi-is-published/)
- [Gravitate Health FHIR Implementation Guide (R4)](https://build.fhir.org/ig/hl7-eu/gravitate-health-ips/)
- [Appnovation — Transforming pharmaceutical labeling with FHIR](https://www.appnovation.com/blog/transforming-pharmaceutical-labeling-digital-epi-fhir-standards)
- [Veeva Vault RIM guide 2026 (IntuitionLabs)](https://intuitionlabs.ai/articles/veeva-vault-rim-guide-2)
- [Veeva Vault pricing 2026 (IntuitionLabs)](https://intuitionlabs.ai/articles/veeva-vault-pricing-2026-cost-breakdown)
- [Veeva Vault RIM alternatives (IntuitionLabs)](https://intuitionlabs.ai/articles/veeva-vault-rim-alternatives)
- [Veeva Vault Help — Working with FHIR Messages](https://regulatory.veevavault.help/en/gr/48830/)
- [IQVIA RIM Smart Content Management](https://www.iqvia.com/solutions/safety-regulatory-compliance/regulatory-compliance/iqvia-rim-smart-content-management)
- [IntuitionLabs — Structured Product Labeling data integrity](https://intuitionlabs.ai/articles/structured-product-labeling-data-integrity)
- [Docuvera — Structured content accelerates ePI readiness](https://docuvera.com/blog/structured-content-epi-readiness/)
- [Docuvera — CMC documentation software (IntuitionLabs)](https://intuitionlabs.ai/software/regulatory-affairs-compliance/cmc-documentation/docuvera)
- [eCTD software comparison (IntuitionLabs)](https://intuitionlabs.ai/articles/ectd-software-comparison)
- [AI in Regulatory Affairs market report (Research and Markets)](https://www.researchandmarkets.com/reports/6226580/ai-in-regulatory-affairs-market-report)
- [AI in Regulatory Affairs market (Straits Research)](https://straitsresearch.com/report/ai-in-regulatory-affairs-market)
- [AI in Regulatory Affairs market (Grand View Research)](https://www.grandviewresearch.com/industry-analysis/artificial-intelligence-ai-regulatory-affairs-market-report)
- [Freyr Solutions — Medicinal products regulatory services](https://www.freyrsolutions.com/medicinal-products)
- [HAPI FHIR — open source FHIR API for Java](https://hapifhir.io/)
- [HL7 FHIR Validator (Confluence)](https://confluence.hl7.org/display/FHIR/Using+the+FHIR+Validator)
- [HL7 Vulcan ePI project](https://hl7vulcan.org/projects/electronic-product-information-epi/)
- [HL7 Global Core ePI IG](https://build.fhir.org/ig/HL7/emedicinal-product-info/)
- [GLAMS ePI](https://www.glams.com/epi)
