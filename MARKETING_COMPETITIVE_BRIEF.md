# Marketing Competitive Brief: Antigravity ePI Backend

**Prepared for:** Marketing, content, and demand-gen teams
**Date:** 2026-04-14
**Upstream doc:** `COMPETITIVE_ANALYSIS.md` (product strategy)
**Scope:** Messaging, narrative, content strategy, channel presence, and sales-enablement assets for a GTM targeting EMA's Q3/Q4 2026 ePI go-live.

---

## 1. Executive Summary

The EMA's phased ePI rollout creates a narrow 6–9 month GTM window (Apr → Dec 2026) before Veeva's August 2026 AI Agents release potentially collapses the point-solution space. Five vendors currently shape the conversation: **Glemser, MT-G, i4i, READY! for ePI, and Datapharm** — plus the **Veeva/IQVIA/Docuvera** suite trio owning "RIM and structured content" share of voice.

**Biggest opportunity:** the "developer-first, stateless API, fidelity-scored" narrative is completely unclaimed in the market. Every competitor either sells a managed service (Glemser, MT-G), a heavy platform (Veeva, i4i), or an end-to-end ePI suite (READY! for ePI). Nobody is positioning as **"the Stripe of ePI conversion."**

**Biggest threat:** Veeva has already shipped FHIR message transmission in 26R1 (April 2026), is hosting its 2,400-attendee R&D & Quality Summit in Boston (May 19–20) and Copenhagen (May 28–29, 2026), and ships **AI Agents for RIM in August 2026** — right inside our launch window. If Veeva bundles DOCX→FHIR into AI Agents, every Vault RIM customer will default to it.

---

## 2. Competitor Profiles

### 2.1 Glemser (Direct — closest functional analog)

**Company overview.** Pennsylvania-based reg-tech vendor with deep pharma CCMS heritage. Offers **ComplianceAuthor** (AI-powered structured content authoring) and an **on-demand FHIR label conversion service** with a 24–48 hour SLA. Collaborates with the Vulcan HL7 FHIR Accelerator and actively publishes ePI thought leadership.

**Messaging analysis.**
- **Primary tagline:** "On-Demand HL7 FHIR Conversion — 24–48 HR Turnaround."
- **Core value proposition:** "Upload your labels → get validated FHIR outputs in 1–2 business days. Scales to thousands."
- **Key themes:** (1) Speed (24–48h), (2) Scale (hundreds-to-thousands), (3) AI-powered (ComplianceAuthor NLP+GenAI), (4) Industry authority (Vulcan FHIR IG co-author).
- **Tone:** Authoritative, reg-ops-practitioner-speaking-to-reg-ops-practitioner, heavy on compliance language.
- **Problem framing:** "MAHs face enormous conversion volume and lack in-house FHIR expertise. A managed portal is the bridge."

**Product positioning.** Category = "ePI FHIR conversion service." Differentiators claimed: (1) GxP-compliant portal, (2) ComplianceAuthor AI, (3) <5 days to onboard, (4) fixed-fee-per-document pricing.

**Content strategy.**
- **Blog cadence:** ~1–2 posts/month on ePI, CCMS, FAIR/FHIR principles, jurisdictional deadlines (Jordan JFDA, EMA).
- **Content formats:** blog posts, "ePI Guide" long-form resource, LinkedIn company posts, press releases on regulatory mandates.
- **SEO targets (inferred):** "ePI FHIR conversion," "FHIR label conversion," "HL7 ePI," "Jordan ePI mandate."
- **Thought leadership themes:** CCMS adoption, structured authoring, global jurisdictional deadlines (UK, Jordan, EMA).

**Strengths.**
- **Functional parity with us** on the core outcome (DOCX → validated FHIR).
- First-mover SEO on "ePI FHIR conversion" terms.
- Active in HL7 Vulcan FHIR Accelerator — industry legitimacy.
- Trusted brand among mid-to-large pharma CCMS buyers.

**Weaknesses.**
- Managed-service model = 1–2 day turnaround, not seconds.
- Portal-based, not API-first. No developer surface.
- No public pricing; every deal requires sales conversation.
- No visible fidelity-score metric — customers must trust the black box.
- LinkedIn presence is corporate-announcement-heavy, low engagement.

---

### 2.2 MT-G (Direct — language-led play)

**Company overview.** German pharmaceutical language-services firm pivoting into structured content and FHIR transformation. Participated in EMA's June 2025 UAT for ePI import.

**Messaging analysis.**
- **Primary tagline:** "We empower you to reach the world." (Language-first framing.)
- **Core value proposition:** "Translation + structured content + FHIR conversion from one pharma-specialist partner."
- **Key themes:** (1) Multilingual expertise (42+ languages), (2) EMA-compliant, (3) Full lifecycle (translate + structure + convert + publish), (4) German precision.
- **Tone:** Formal, consulting-led, pharma-regulatory voice.

**Product positioning.** Category = "pharma language service with FHIR transformation." Differentiators: translation bundled, professional consulting, EMA UAT participant.

**Content strategy.** Low blog cadence; leads with consulting collateral and industry event presence (pharma conferences, ePI roundtables).

**Strengths.** Credibility with EU MAHs that have multi-language labelling needs. EMA UAT participation is a trust signal.

**Weaknesses.** Translation-first framing does not resonate with tech buyers. No self-serve path. Slowest turnaround of any direct competitor.

---

### 2.3 i4i (Direct — platform play)

**Company overview.** "The structured content company." Full global labeling platform supporting US SPL, Health Canada XML PM, and FHIR ePI. Targets enterprise labeling teams.

**Messaging analysis.**
- **Primary tagline:** "The structured content company."
- **Core value proposition:** "One platform for every jurisdiction's structured label output — SPL, XML PM, FHIR ePI."
- **Key themes:** (1) Multi-jurisdiction, (2) Central label repository, (3) Content reuse, (4) End-to-end (authoring → submission formatting).
- **Tone:** Enterprise-platform-speak. Buyer is VP of Labeling.

**Strengths.** Broadest jurisdictional coverage. Real customers shipping SPL today. Content-reuse story resonates with large pharma.

**Weaknesses.** Heavy platform; long implementation cycles. No developer-first story. FHIR ePI is one of several output formats, not the headline.

---

### 2.4 READY! for ePI (NNIT) (Direct — ePI-dedicated suite)

**Company overview.** NNIT-backed ePI authoring (DiCE) + FHIR Gateway for EMA transmission. Positioned as "purpose-built for ePI end-to-end."

**Messaging analysis.**
- **Primary tagline:** "READY! for ePI."
- **Core value proposition:** "From draft to EMA submission, one integrated ePI path."
- **Key themes:** (1) Purpose-built for ePI (not general SCA), (2) Submission gateway included, (3) FHIR-native from day one.

**Strengths.** Only vendor with an ePI-dedicated brand name. Submission-gateway integration closes the last mile.

**Weaknesses.** Narrow to ePI only — doesn't serve teams that also need SPL or other jurisdictions. NNIT brand is strong in Nordic pharma but less globally.

---

### 2.5 Datapharm / emc (Direct — UK-ecosystem play)

**Company overview.** UK operator of emc.uk (medicines.org.uk), the primary consumer-facing SmPC/PIL display surface. Gravitate Health partner; operates live FHIR conversion for emc content.

**Messaging analysis.**
- **Tagline theme:** "The dissemination of your medicine information is about to change lives."
- **Narrative arc:** patient-outcome-focused (ePI → better healthcare access → lives changed). Not reg-ops-pitched.

**Strengths.** Deep ecosystem embedding (Gravitate Health, EU network). Patient-outcome narrative resonates with medical-affairs buyers.

**Weaknesses.** UK-centric. Positioned as distribution network operator, not as a vendor MAHs procure conversion from. Less direct competitor, more infrastructure partner.

---

### 2.6 Veeva Vault RIM (Indirect — the 800-lb gorilla)

**Company overview.** The RIM platform of record for life sciences; top-20 pharma customer base; 26R1 release (April 2026) added FHIR message transmission to PMS; **AI Agents for RIM GA August 2026**.

**Messaging analysis.**
- **Primary tagline:** "The only cloud platform built for life sciences."
- **Key themes for 2026:** (1) AI Agents, (2) IDMP compliance (June + December 2026 deadlines), (3) eCTD 4.0, (4) end-to-end regulatory cloud.
- **Event presence:** 2,400+ at R&D & Quality Summit (Boston May 19–20; Copenhagen May 28–29; Boston Oct 20–21, 2026). 100+ breakout sessions.

**Content strategy.** Massive. Daily LinkedIn activity, quarterly analyst days, publishes customer-story case-study engine, owns the "life sciences cloud" SEO position. Every reg-ops buyer sees Veeva content.

**Strengths.** Incumbency, platform gravity, AI-Agents roadmap, massive event footprint, senior-buyer mindshare.

**Weaknesses.** Slow implementation (6–12 months). Six-figure contracts. Horizontal focus — FHIR ePI is one feature of many, not a specialist product. CrossLink + FHIR message submission is manufacturing-enrichment-only today.

---

### 2.7 Docuvera (Indirect — AI-native SCA)

**Messaging analysis.**
- **Tagline:** "AI-powered Structured Content Authoring."
- **Themes:** component-based reuse, eCTD 4.0 + ePI + DADI + FHIR alignment, "built for the structured future."
- **Content:** active blog with "why clinical transformation will fail without structured content" thought-leadership pieces. LinkedIn-heavy strategy.

**Strengths.** Modern AI-native brand, fast-moving, resonates with next-gen reg-ops leaders.

**Weaknesses.** SCA tool, not a conversion API. Requires component authoring commitment from customer.

---

### 2.8 Freyr / ProductLife / Accenture Life Sciences (Substitute — CRO services)

**Messaging analysis.**
- **Themes:** "full-service regulatory outsourcing," "1,850+ clients," "30% cost savings," "scale without headcount."
- **Channel:** sales-led, long RFP cycles, relationship-driven.

**Strengths.** Trusted by reg-ops buyers who want one accountable vendor. Scale headcount.

**Weaknesses.** Per-document costs are highest in the market. Slow (3–5 days). Black-box process. Not a product — a service.

---

## 3. Messaging Comparison Matrix

| Dimension | **Antigravity ePI Backend (us)** | Glemser | MT-G | i4i | READY! for ePI | Veeva Vault RIM | Docuvera | Freyr (CRO) |
|---|---|---|---|---|---|---|---|---|
| **Primary tagline** | *"The Stripe of ePI conversion"* (proposed) | "On-demand HL7 FHIR conversion, 24–48 hr turnaround" | "We empower you to reach the world" | "The structured content company" | "READY! for ePI" | "The only cloud platform built for life sciences" | "AI-powered structured content authoring" | "Your regulatory partner" |
| **Target buyer** | Reg-tech engineering leads, CRO CTOs, mid-cap MAH platform teams | Reg-ops / labeling director at mid-large pharma | EU regulatory labeling manager, multilingual | VP of Global Labeling, enterprise | ePI program lead, EMA submissions | VP RIM / Head of Regulatory Ops, top-50 pharma | Head of Regulatory Content, innovation-led teams | VP Regulatory Affairs, mid-cap |
| **Category claim** | FHIR conversion API | ePI FHIR conversion service | Pharma language service + FHIR | Global labeling platform | ePI authoring + submission gateway | Life sciences cloud / RIM | Structured content authoring | Regulatory outsourcing |
| **Key differentiator** | Stateless API + <30s + fidelity score + audit log | 24–48h SLA, GxP portal | Language + FHIR bundled | Multi-jurisdiction (SPL + XML PM + FHIR) | End-to-end ePI incl. gateway | Platform breadth + AI Agents | AI-native + modular components | Full-service outsourcing |
| **Tone/voice** | Developer-empathic, quantitative, transparent | Compliance-authority, practitioner | Formal, German-pharma, consulting | Enterprise-platform | Program-manager clear | Cloud-platform confident | Innovation-led, future-tense | Partner-accountable |
| **Villain in their narrative** | "Multi-month suite implementations and black-box conversion services" | "Manual conversion at ~10 hrs/document" | "Fragmented language + structure + conversion vendors" | "Jurisdiction-specific tool sprawl" | "ePI left unfinished at submission" | "Fragmented legacy regulatory stacks" | "File-based document workflows" | "In-house headcount shortage" |
| **Hero in their narrative** | The engineer shipping an ePI-ready product in weeks | The reg-ops team that hits deadline | The multilingual regulatory team | The global labeling organisation | The ePI program lead | The modern life-sciences CIO | The innovation-led reg-ops team | The MAH scaling without hiring |
| **Transformation promise** | "Document → validated FHIR bundle in under 30 seconds, with a fidelity score you can show your auditor" | "Upload → validated FHIR in 24–48 hours" | "One partner from source Word → multilingual FHIR ePI" | "Author once, publish to every jurisdiction" | "From draft to EMA in one path" | "Run your entire RIM on one cloud" | "Components you reuse across every output" | "Scale conversion without hiring" |
| **Primary CTA** | "Try the API — first 25 conversions free" (proposed) | "Request access" | "Request consultation" | "Request demo" | "Request demo" | "Request demo" | "See it live" | "Contact sales" |
| **Pricing transparency** | Published per-call (proposed) | Opaque, quote-based | Opaque | Opaque | Opaque | Opaque (six-figure annual) | Opaque | T&M |
| **Self-serve sandbox** | Yes (proposed) | No | No | No | No | No | No | No |

---

## 4. Content Gap Analysis

### Topics competitors are covering heavily

| Topic | Glemser | MT-G | i4i | READY! | Veeva | Docuvera | Gap for us? |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| EMA ePI Q3/Q4 2026 go-live timeline | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Parity — we must play |
| Jordan JFDA ePI mandate | ✅ | | ✅ | | | | Parity — secondary play |
| CCMS / structured content authoring | ✅ | | ✅ | | ✅ | ✅ | **Low priority for us** (not our category) |
| eCTD 4.0 transition | | | ✅ | | ✅ | ✅ | Low priority |
| IDMP June/December 2026 deadlines | | | ✅ | | ✅ | | Low priority |
| FHIR 101 for pharma | ✅ (Datapharm too) | ✅ | ✅ | ✅ | | ✅ | **Parity — must-play** |
| AI for regulatory affairs | ✅ | | | | ✅ | ✅ | **Parity — must-play** |

### Topics nobody is covering well — our white-space plays

| Topic | Why it's open | Our advantage |
|---|---|---|
| **"Building an ePI pipeline in an afternoon" (developer tutorial)** | No competitor has developer-tutorial content | We have an actual API with OpenAPI docs |
| **"How to audit an AI-converted FHIR document"** | Nobody frames auditability as a product feature | Our fix audit log is uniquely structured |
| **"Fidelity scoring: the missing KPI in ePI conversion"** | Nobody publishes or commits to a fidelity score | We have a recall-based 0–100 score built in |
| **"ePI conversion under 30 seconds: a benchmark"** | Glemser's 24–48h framing is the industry default | We are ~5,000× faster |
| **"ePI for CROs: OEM the conversion layer"** | No competitor positions to CROs as a platform | We can be their backend |
| **"Open-source vs. API: the ePI conversion build-vs-buy decision"** | Nobody compares HAPI DIY to their product | We can lead this honest comparison |
| **"Embedding FHIR conversion inside Vault RIM workflows"** | Nobody positions as Veeva-complementary | De-risks the incumbent threat |

### Content formats we should prioritise (vs. what competitors use)

| Format | Glemser | Veeva | Docuvera | Us (recommended) |
|---|:---:|:---:|:---:|:---|
| Blog posts | Heavy | Heavy | Heavy | Match with developer-tutorials style |
| Long-form "ePI Guide" | Yes | Yes | Yes | **Must-have: "The ePI Conversion Engineer's Handbook"** |
| LinkedIn corporate | Heavy | Very heavy | Heavy | Match cadence, differentiate tone |
| Webinars | Occasional | Monthly | Occasional | Monthly technical deep-dives |
| Case studies | Some | Industrial | Some | 2–3 design-partner stories in 6 months |
| Podcast | No | No | No | **White-space: launch "The ePI Engineer" 10-ep series** |
| Developer docs / API reference | No | Limited (customers only) | No | **White-space: public OpenAPI reference** |
| Interactive tools / benchmarks | No | No | No | **White-space: "Score your SmPC" self-serve fidelity check** |
| Open-source / GitHub repos | No | No | No | **White-space: OSS sample client SDKs** |

---

## 5. Opportunities (Marketing Angles to Own)

1. **"Stateless API, sub-30-second" positioning** — own the speed-and-shape differentiator. Benchmark publicly against Glemser's 24–48 hour SLA.
2. **Auditability as product feature** — "Every fix logged with rule ID, location, before/after." Publish the fidelity score publicly, commit to a threshold. GxP-buyer credibility.
3. **Developer-first content surface** — OpenAPI docs, sandbox, Postman collection, SDK repos. No competitor is doing this.
4. **CRO OEM partnership narrative** — position as distribution layer for Freyr, ProductLife, Accenture. "We power the conversions behind your ePI service."
5. **Veeva-complementary narrative** — do not attack Veeva; position as embeddable inside Vault RIM. Catches Vault customers during the August 2026 AI Agents decision.
6. **"Fidelity score" as industry category-defining metric** — push the FHIR conversion market to commit to a 0–100 recall score, the way Core Web Vitals redefined web performance.
7. **Engineering-led thought leadership** — "The ePI Engineer" podcast, HL7 FHIR Connectathon presence, open GitHub samples. Owns the engineering-audience share of voice nobody else is fighting for.

---

## 6. Threats (What Could Kill Our GTM)

1. **Veeva AI Agents for RIM (GA August 2026)** — could add DOCX→FHIR natively inside Vault; Vault customers default to incumbent. **Mitigation:** ship Veeva-complementary connector narrative and reference architecture *before* Aug 2026 launch.
2. **Glemser's SEO incumbency on "ePI FHIR conversion"** — their content is 2–3 years old and ranks. **Mitigation:** build a distinct keyword frontier ("FHIR conversion API," "ePI audit log," "FHIR fidelity score") rather than head-to-head on their terms.
3. **EMA mandate slipping beyond Q4 2026** — demand pressure drops, buyers revert to "wait and see." **Mitigation:** reposition to the non-mandate use cases (multilingual PIL updates, post-approval SmPC changes, emc display integrations).
4. **Gravitate Health reference implementation reaching production** — could commoditise conversion as free infrastructure. **Mitigation:** lead on what a reference impl won't have — enterprise auth, SLA, audit log, support.
5. **AI-native reg-tech startup enters** — a Glemser competitor with an API-first posture could land in the same white space we plan to occupy. **Mitigation:** move first on developer content and benchmarks; claim category language.
6. **GxP audit rejection of rule-based auto-fixing** — a single high-profile rejection story could taint the category. **Mitigation:** publish the audit-log schema publicly; work with a regulatory SME for sign-off case study.

---

## 7. Recommended Actions

### Quick wins (this week)

1. **Draft the three signature messaging assets:**
   - Homepage H1 + subhead around the "Stripe of ePI conversion" idea.
   - One-page competitor landing: "ePI Backend vs. Glemser" (honest comparison, our speed/auditability wins, their managed-service strengths).
   - LinkedIn founder post announcing the fidelity-score benchmark and inviting design partners.
2. **Stand up a public sandbox + OpenAPI reference** at `api.antigravity.dev/epi/docs` (or similar). No competitor has this.
3. **Claim the keyword frontier:** register targets for `FHIR conversion API`, `ePI audit log`, `FHIR fidelity score`, `SmPC to FHIR API`, `DOCX to FHIR`.
4. **Secure DIA RSIDM Forum 2026 follow-up content** (Feb 2–4, 2026 already happened; the next one is 2027 — instead focus on DIA Europe 2026 regulatory-operations track and post-event content).

### Strategic moves (90–180 days)

5. **Launch "The ePI Engineer" podcast/newsletter** — 10 episodes, interviewing HL7 contributors, Gravitate Health leads, CRO CTOs. Seed it at DIA Europe 2026.
6. **Publish the "ePI Conversion Engineer's Handbook"** — long-form, open, Markdown + PDF; becomes the reference asset that drives top-of-funnel. Include a vendor comparison (including us).
7. **Ship two design-partner case studies** — one mid-cap MAH, one CRO OEM — showing end-to-end outcome.
8. **Run a live, public FHIR fidelity benchmark** — upload 10 known-good SmPCs, publish each vendor's fidelity score (ours, and any vendor that opts in). Creates a category metric. Echoes Core Web Vitals playbook.
9. **Sponsor / speak at Veeva R&D Summit Copenhagen (May 28–29, 2026)** — not as a booth but as a sponsored talk on "embedding FHIR conversion inside Vault RIM" — catches the incumbent buyer mid-evaluation.
10. **Set up competitive monitoring** — weekly Glemser/Veeva/Docuvera blog + LinkedIn alerts; monthly feature/pricing scan; real-time Google Alerts on "`hl7.eu.fhir.epil`," "ePI conversion," competitor brand + "pricing."

---

## 8. Battlecard Summary (sales-enablement snapshot)

### vs. Glemser

**Their pitch:** "Managed ePI FHIR conversion, 24–48 hour SLA, GxP portal."
**Their strengths:** Trust, SEO, Vulcan FHIR IG authorship.
**Their weaknesses:** Portal-only, opaque pricing, no fidelity score published, batch not real-time.
**Our differentiators to lead with:** (1) Real-time API (seconds not days), (2) published fidelity score, (3) transparent per-call pricing, (4) audit log you can diff in git.
**Objection handling:**
- *"Glemser is more trusted."* → "They're a great managed-service partner. We're for teams that need to embed conversion into their own product, CRM, or CI/CD — which is a different product shape."
- *"Glemser has GxP."* → "Our audit log is a GxP-ready transformation ledger from day one. We'll walk your QA auditor through the structure."
**Landmine to set:** "How long does your current vendor take per document, and can you see the diff between what you submitted and what they produced?"

### vs. Veeva Vault RIM

**Their pitch:** "Life-sciences cloud, AI Agents GA Aug 2026."
**Their strengths:** Incumbency, breadth, top-20 pharma customer logos.
**Their weaknesses:** 6–12 month implementation, six-figure contracts, AI Agents is horizontal (not FHIR-focused).
**Our play:** **Complementary, not competitive.** Sell to Vault customers as the embeddable conversion layer inside their existing RIM.
**Objection handling:**
- *"We're already on Vault."* → "Great — we run alongside. Here's a reference architecture showing how our API feeds Vault Submissions while preserving your existing workflow."
- *"We'll wait for AI Agents."* → "AI Agents is powerful for document intelligence. FHIR ePI conversion is a very specific pipeline; ours is production-ready today with a published fidelity score. Pilot both and compare."
**Landmine to set:** "If AI Agents doesn't ship DOCX→FHIR conversion in the Aug release, what's your Q4 plan?"

### vs. CROs (Freyr / ProductLife / Accenture)

**Their pitch:** "Full-service outsourcing, 30% savings, 1,850+ clients."
**Our play:** **Turn them into a distribution channel.** OEM partnership where they wrap our API as their backend.
**If selling direct to an MAH considering a CRO:** "CROs shine on dossier-level services. For raw conversion throughput, direct API gives you 100× the speed and lets you keep conversion inside your stack."

---

*End of brief.*

## Sources

- [Glemser — On-demand HL7 FHIR conversion](https://glemser.com/on-demand-hl7-fhir-conversion-services/)
- [Glemser — ePI Guide](https://glemser.com/epi-guide/)
- [Glemser — Embracing ePI blog](https://glemser.com/blog/epi-the-future-of-pharmaceutical-labeling-has-arrived/)
- [Glemser — CCMS blog](https://glemser.com/blog/redefining-content-management-component-content-management-systems-ccms/)
- [Glemser — JFDA / Jordan ePI mandate](https://glemser.com/news/jordan-epi-leaflet-mandate-2025/)
- [Glemser LinkedIn](https://uk.linkedin.com/company/glemser-technologies)
- [MT-G — FHIR ePI service](https://www.mt-g.com/en/language-solutions/we-empower-you-to-reach-the-world/electronic-product-information)
- [i4i — structured content company](https://www.i4i.com/)
- [READY! for ePI](https://www.ready4epi.com/)
- [Datapharm — FHIR 101 for pharma](https://www.datapharm.com/resource-hub/fhir-101-pharmas-guide-to-the-emerging-standard-in-healthcare-information/)
- [Docuvera — structured content ePI readiness](https://docuvera.com/blog/structured-content-epi-readiness/)
- [2026 Veeva R&D and Quality Summit (Boston May 19–20, Copenhagen May 28–29)](https://www.veeva.com/events/rd-summit/)
- [Veeva EU R&D Summit 2026](https://www.veeva.com/eu/events/rd-summit/overview/)
- [Veeva Vault FHIR Messages](https://regulatory.veevavault.help/en/gr/48830/)
- [DIA Europe 2026 — Regulatory Operations track](https://www.diaglobal.org/en/flagship/dia-europe-2026/program/schedule/tracks/regulatory-operations)
- [DIA RSIDM Forum 2026](https://www.extedo.com/events/dia-regulatory-submissions-information-and-document-management-forum-2026)
- [EMA ePI overview](https://www.ema.europa.eu/en/human-regulatory-overview/marketing-authorisation/product-information-requirements/electronic-product-information-epi)
- [Gravitate Health FHIR IG](https://www.gravitatehealth.eu/fhir-implementation-guide-for-epi-is-published/)
