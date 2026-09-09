# SPEC DRAFT — P1-IMG: Images from uploaded DOCX → contained FHIR Binary in the final XML

**Status:** DRAFT for review · **Date:** 2026-09-08 · **Author:** Claude (Cowork) for Syo · **Applies to:** `FEATURE_SPEC.md` v2.0.0, `CLAUDE.md` v1.0
**Operating under:** `CLAUDE.md` §6 (spec first, test first), §5 (no regressions), §5.7 (feature flag), §9.3/§9.4 (narrative + mapping rules)

How to use this file: every block under §2–§7 is written to be pasted verbatim. §2 → `FEATURE_SPEC.md`, §3 → `CLAUDE.md`, §4 → `CHANGELOG.md`, §5 → `Dockerfile` / `requirements.txt`, §6 → new test files (they FAIL today, by design), §7 → hand-off prompt for the implementation session. Nothing here has been applied to the repo.

---

## 1. Decision record

### 1.1 What the standards say

| Source | Rule | Where |
|---|---|---|
| HL7 ePI IG — Tech Style Guide | "All images must be embedded as Base64 objects within a **Contained Binary resource**." SVG preferred; PNG/JPEG "acceptable for legacy content only". `alt` text always. No fixed dimensions. | build.fhir.org/ig/HL7/emedicinal-product-info/en/tech-style-guide.html#images |
| HL7 ePI IG — Build Type 1, step 4 | "Add a `Binary` resource in `contained`, reference it with `<img src="#id"/>` in the narrative." Never link to external files. | …/en/build-epi1.html |
| HL7 ePI IG — Best Practice | ≤ ~140-char alt text, no "image of…", WCAG AA contrast. | …/best-practice.html |
| HL7 ePI IG — `binary-epi` profile | `Binary.contentType` 1..1 (MimeTypes VS), `Binary.data` 1..1, `Binary.securityContext` 0..0. | …/en/StructureDefinition-binary-epi-definitions.html |
| FHIR R5 core — Narrative | `data:` URLs are also spec-legal, but "the source for any images that are an essential part of the narrative SHOULD always be embedded as a data: url, in an attachment or a contained resource". | hl7.org/fhir/narrative.html#id |
| **EU IG `EUePI` 1.0.0 (in `resources/package/`)** | `Composition.contained` short text: **"Images in ePI Composition documents included as contained binary resources."** 0..\* | `StructureDefinition-EUEpiComposition.json` |
| **EU IG `EUePI` 1.0.0** | `Composition.extension:imageReference` 0..\* — `http://ema.europa.eu/fhir/StructureDefinition/ext-epi-image-reference`, `valueReference` → the Binary. | `StructureDefinition-ext-epi-image-reference.json` |
| **EMA validated sample EPI-25-100 (May 2025, in `resources/`)** | SmPC + PL Compositions each carry 3 `contained` Binaries (`image/png`, `image/jpeg`). Every `<img>` has exactly two attributes: `src="#<uuid>"`, `alt="…"`. No `data:` URIs. The `imageReference` extension is **not** used in the sample. | `epi-25-100-sample/English_ePI_Sample_BundleCollection.xml` |

Neither the HL7 IG nor the EU IG defines any image *manifest* outside the FHIR resources themselves. The Binary (`id`, `contentType`, `data`) plus the optional `imageReference` extension **is** the manifest.

### 1.2 What the code does today

`doc_parser.convert_image` (L201) inlines every DOCX image as `<img src="data:<mime>;base64,…">`. The sanitiser leaves `img/src/alt` untouched; `_fix_self_closing_tags` makes it XHTML-void; the base64 rides inside `Composition.section.text.div`. No `Binary` is created anywhere. `alt` appears only if the DOCX author set alt text. No golden fixture contains an image, so the validator has never seen this path.

### 1.3 Decisions (confirmed with Syo, 2026-09-08)

| # | Decision | Rationale |
|---|---|---|
| D1 | Images become `Composition.contained` Binary resources referenced as `<img src="#<id>" alt="…"/>`. `data:` URIs never reach the emitted XML when the feature is on. | EU IG + EMA sample + HL7 IG all agree. CLAUDE.md §11 #14 (prefer validator-clean Option B). |
| D2 | Non-web-safe formats (EMF/WMF/TIFF/BMP/GIF/WebP…) are **rasterised to PNG server-side**. Pillow for Pillow-readable formats; LibreOffice Draw headless for EMF/WMF. If conversion fails, the original bytes are preserved as a Binary with their real MIME type and flagged — never dropped. | Syo's choice. ALCOA+ "Original/Complete": no silent data loss. |
| D3 | Missing/empty `alt` → placeholder `alt="Figure N"` + `IMG-ALT-MISSING` audit row so QA reviews it. | Syo's choice. IG makes alt mandatory; a flagged placeholder is honest, silence is not. |
| D4 | **No new top-level response field.** The 21-field contract stays frozen. Evidence goes to (a) the bundle itself (contained Binary + `imageReference` extensions) and (b) `fix_log` rows with `IMG-*` rule IDs at `iteration: 0`. | Syo asked to check the IG: it has no manifest concept beyond the Binary. Adding a field would be product invention, not conformance. Reversible later (additive). |
| D5 | Binary `id = "img-" + sha256(final bytes)[:32]`. Byte-identical images share one Binary. | CLAUDE.md §4.4 reproducible runs; contained-id uniqueness for free. |
| D6 | We also emit `Composition.extension:imageReference` (one per Binary, `#<id>`). | Defined by the EU IG package we validate against; gives a machine-readable image list without a new API field. If the validator flags it, drop per the §9.4 domain-extension precedent (Open Question 21). |
| D7 | Ships behind per-tenant flag `IMAGE_BINARIES_TENANTS_ALLOWLIST`, default off. Flag-off output is byte-identical to today. | CLAUDE.md §5.7 — changes a regulated output (FHIR mapping). |
| D8 | Embedding happens at **mapping time** (before Phase 1), not as a fixer. `original_xml`, `xml` and `bundle_xml` all carry the Binaries. | CLAUDE.md §5.3 — Phase 1 must validate the XML that ships. |

---

## 2. `FEATURE_SPEC.md` — paste blocks

### 2.1 §4 User Stories — append

```markdown
15. **As a regulatory-operations user uploading an SmPC that contains figures** (chemical structures, dosing diagrams, device-handling pictograms), I want every image to arrive in the ePI bundle as a self-contained `Binary` resource with accessible alt text, so that the bundle validates against the EU IG, renders on the EMA portal exactly as the EMA samples do, and I can see in the fix log which images were converted or need an alt-text review.
```

### 2.2 §5 Should-Have (P1) — insert after P1-PUB-4

```markdown
#### P1-IMG-1. Images as contained Binary resources
**Given** a DOCX whose parser output contains `<img src="data:<mime>;base64,…">` elements, **when** the tenant is on `IMAGE_BINARIES_TENANTS_ALLOWLIST` and the document is mapped by `fhir_mapper.create_doc_composition(…, embedder=ImageEmbedder())`, **then**:
- each distinct image (by SHA-256 of its final bytes) becomes exactly one `Binary` in `Composition.contained` with `id = "img-" + sha256(final_bytes)[:32]`, `contentType` = final MIME type, `data` = base64 of the final bytes — in first-appearance document order;
- every `<img>` in `Composition.text.div` (preface) and every `Composition.section[…].text.div` is rewritten to `<img src="#<id>" alt="<alt>"/>` carrying **exactly** the attributes `src` and `alt` (width/height/style/class stripped — styling is the stylesheet's job, CLAUDE.md §9.3);
- one `Composition.extension` per Binary with `url = http://ema.europa.eu/fhir/StructureDefinition/ext-epi-image-reference` and `valueReference.reference = "#<id>"`, in the same order as `contained`;
- no `data:` URI remains anywhere in `original_xml`, `xml`, `bundle_xml`, `bundle_json`, or `source_text`;
- `ImageEmbedder.process` is idempotent — `process(process(html)) == process(html)` — and a no-op input is returned byte-equal (CLAUDE.md §5.5, §7.3);
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
- EMF/WMF convert via LibreOffice Draw headless (`soffice --headless --convert-to png`), one invocation per request for all EMF/WMF images, with a private `-env:UserInstallation` per request (no profile-lock collisions under concurrency), 15 s total timeout, 300 DPI, longest side capped at 2400 px (Open Question 19).
- Every PNG — converted or re-encoded — passes through `normalise_png()` (decode → re-save, no ancillary text/time chunks, fixed encoder settings) so the bytes are deterministic for a pinned Pillow version.
- SVG passes through untouched **only** if it contains no `<script`, no `on*=` attributes and no external `href`/`xlink:href`; otherwise it is rasterised. An SVG that fails both checks and conversion is preserved and flagged `IMG-SVG-UNSAFE` **and** `IMG-FORMAT-UNSUPPORTED`.
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
- **Contract.** The response keeps exactly the 21 keys of user story 8 (23 with `publish: true`). No key is added, renamed, or retyped. `fix_log` remains a list of four-key dicts.
- **Pipeline.** Embedding is a mapping-time transform; Phase 1 → Phase 2 order and all constants are untouched (CLAUDE.md §5.3). `_compute_fidelity` strips tags before tokenising, so images contribute zero words; the image-bearing fixture must score within 0.5 of its image-free sibling (CLAUDE.md §5.8).
- **Side effect (documented).** `ImageEmbedder.process` rewrites `doc["sections"][i]["text"]` **in place** so `source_text` and `generate_bundle` see `#id` references without a second embedding pass. `generate_bundle(doc_list, embedder=…)` reuses the same embedder; `process` on already-rewritten text is a no-op.

*Acceptance criteria:*
- Given the fixture, then `fix_log` contains 4 × `IMG-EMBED`, 1 × `IMG-ALT-MISSING`, 1 × `IMG-RASTERISE`, 0 × `IMG-FORMAT-UNSUPPORTED`, all with `iteration == 0` and a non-empty `location`.
- Given flag on or off, then `set(response.keys()) == the 21 baseline fields`.
- Given the flag off, then no `IMG-*` row exists and `xml` still contains `data:image/`.
- Given `original_xml`, then it already contains the 3 Binaries (validated as shipped).
```

### 2.3 §5 Future Considerations (P2) — append

```markdown
- **P2-IMG-1. Vector-preserving EMF/WMF → SVG.** Replace PNG rasterisation for EMF/WMF with an SVG conversion (LibreOffice `--convert-to svg` + sanitisation) so chemical structures stay lossless, per the IG's "SVG preferred". Requires an SVG sanitiser with its own idempotency tests and a Reg SME check that EMA renders SVG.
- **P2-IMG-2. Localised and caption-derived alt text.** Emit the placeholder in the document language (`Abbildung N`, `Figure N`, …) using the language detected for P2-PUB-PORTAL, and propose alt text from an adjacent caption paragraph for reviewer acceptance (never auto-accepted — labelling content, CLAUDE.md §10 #9).
- **P2-IMG-3. Image QA surface.** Reviewer UI listing each Binary with thumbnail, source MIME, conversion path, alt status; pairs with the P2-4 incremental API so alt text can be corrected without re-uploading the DOCX.
```

### 2.4 §7 Code Traceability Matrix — append rows

```markdown
| P1-IMG-1. Contained Binary embedding | `image_embedder.py` (new), `fhir_mapper.py` | `ImageEmbedder.process`, `BinaryRecord`, `binary_id_for`, `EXT_IMAGE_REFERENCE`; `create_doc_composition(…, embedder=)` attaches `contained` + `extension:imageReference`; `generate_bundle(…, embedder=)`; `_json_to_xml` emits `<contained><Binary>` |
| P1-IMG-2. Rasterisation | `image_embedder.py`, `Dockerfile`, `requirements.txt` | `WEB_SAFE_MIME`, `to_png`, `normalise_png`, `_libreoffice_to_png`, `ImageConversionError`; `Pillow` pin; `libreoffice-draw` + `fonts-dejavu-core` layers |
| P1-IMG-3. Alt text | `image_embedder.py` | ordinal counter in `ImageEmbedder`, `IMG-ALT-MISSING` |
| P1-IMG-4. Audit / flag / contract | `image_embedder.py`, `main.py` | `ImageAction`; `IMAGE_BINARIES_TENANTS_ALLOWLIST` check next to the publish allowlist; `fix_log` prepend at `iteration 0`; `source_text` built after `create_doc_composition` |
```

And extend the closing sentence of §7: `… or tests/unit/test_image_binaries.py + tests/contract/test_image_contract.py for P1-IMG-*`.

### 2.5 §8 Open Questions — append

```markdown
19. **(Blocking — Regulatory SME, before P1-IMG ships to a design partner)** Rasterisation parameters for EMF/WMF (default 300 DPI, longest side ≤ 2400 px). Does EMA impose a resolution, colour-space or size limit on ePI images? The IG only says "clear and easy to read" and "no resizing by the stylesheet". Source: P1-IMG-2.
20. **(Non-blocking — Regulatory + UX)** Placeholder alt text `Figure N` is English. For non-English SmPCs, do we localise the word (`Abbildung`, `Figura`, …) from the detected document language, or keep a language-neutral token? Source: P1-IMG-3, P2-IMG-2.
21. **(Non-blocking — Engineering)** We emit `Composition.extension:imageReference` because the EU IG package defines it (0..\*), but the EMA validated sample EPI-25-100 does not use it. Confirm the validator is silent; if it warns, drop it following the §9.4 domain-extension precedent and record the decision here. Source: P1-IMG-1 D6.
22. **(Non-blocking — Engineering + Reg SME)** No hard cap on Binary payload size in v1 (informational `IMG-SIZE-LARGE` at 1 MiB). What is EMA's bundle size limit for portal ingestion, and does Render's 30 s budget survive a 20-figure SmPC? Source: P1-IMG-2.
23. **(Non-blocking — QA)** We need one real ChemDraw-exported EMF and one WMF from a design partner for `tests/fixtures/images/`. The synthetic corpus covers TIFF only. Source: P1-IMG-2 AC 5.
```

### 2.6 §5 P0-3 — one-sentence edit

Replace `Images are inlined as base64 (`convert_image`).` with:
`Images are inlined as base64 `data:` URIs by `convert_image` — this is the parser-level intermediate only; P1-IMG-1 turns them into contained Binary resources at mapping time when the tenant flag is on.`

---

## 3. `CLAUDE.md` — paste blocks

### 3.1 §1.3 canonical inventory — add / amend

```markdown
- **`image_embedder.py`** — P1-IMG. `ImageEmbedder` rewrites `<img src="data:…">` → `<img src="#img-<sha256[:32]>" alt="…"/>`, collects `BinaryRecord`s for `Composition.contained`, rasterises non-web-safe formats to PNG (Pillow; LibreOffice Draw headless for EMF/WMF), emits `ImageAction` audit rows (`IMG-*`). Deterministic ids; idempotent.
```
Amend the `fhir_mapper.py` line: append `Images → \`Composition.contained\` Binary + \`extension:imageReference\` when an \`ImageEmbedder\` is passed (P1-IMG-1).`
Amend the `doc_parser.py` line: append `\`convert_image\` emits \`data:\` URIs as the parser-level intermediate.`

### 3.2 §9.3 XHTML narrative discipline — add bullet

```markdown
- Every `<img>` MUST be `<img src="#<contained Binary id>" alt="<non-empty>"/>` — exactly those two attributes, self-closed. No `data:` URIs, no external URLs, no width/height/style. Missing alt gets `Figure N` **and** an `IMG-ALT-MISSING` audit row; it is never silently absent. (HL7 ePI Tech Style Guide § Images; EU IG `EUEpiComposition.contained`.)
```

### 3.3 §9.4 FHIR mapping rules — add bullets

```markdown
- Images live in `Composition.contained` as `Binary { id, contentType, data }` — never as separate Bundle entries, never as `data:` URIs — matching EMA sample EPI-25-100. `id = "img-" + sha256(final bytes)[:32]`; identical bytes share one Binary.
- `Binary.contentType` MUST be one of `image/png | image/jpeg | image/svg+xml` after rasterisation; anything else is a flagged fallback (`IMG-FORMAT-UNSUPPORTED`), not a silent pass.
- One `Composition.extension` `ext-epi-image-reference` per Binary, `valueReference = "#<id>"`, same order as `contained`.
```

### 3.4 §9.6 Logging — add sentence

`Image transformations are logged as fix_log rows at iteration 0 with rule IDs IMG-EMBED / IMG-RASTERISE / IMG-ALT-MISSING / IMG-FORMAT-UNSUPPORTED / IMG-SVG-UNSAFE / IMG-SIZE-LARGE; descriptions carry MIME, byte count and sha256[:12] before and after.`

### 3.5 Header

`**Last updated:** 2026-09-08 · **Version:** 1.1` (also closes the stale-header drift item open since 2026-06-08).

---

## 4. `CHANGELOG.md` — under `[Unreleased] / Added`

```markdown
- **P1-IMG-1..4.** Images in an uploaded DOCX are emitted as `Composition.contained` `Binary` resources referenced from the narrative as `<img src="#img-<sha256[:32]>" alt="…"/>`, with one `ext-epi-image-reference` extension per Binary — the pattern used by the EU IG (`EUEpiComposition.contained`) and EMA sample EPI-25-100. Non-web-safe formats (TIFF/BMP/GIF/EMF/WMF…) are rasterised to PNG (Pillow; LibreOffice Draw headless for EMF/WMF); on conversion failure the original bytes are preserved and flagged. Missing alt text gets `alt="Figure N"` plus an `IMG-ALT-MISSING` audit row. All image transformations appear in `fix_log` as `iteration: 0` rows with `IMG-*` rule IDs. **No new response field** — the 21-field shape is unchanged. Gated by `IMAGE_BINARIES_TENANTS_ALLOWLIST` (default off; flag-off output byte-identical to v2.0.0).
- New module `image_embedder.py`; new fixture `tests/fixtures/synthetic_smpc_images.docx` (+ generator); new tests `tests/unit/test_image_binaries.py`, `tests/contract/test_image_contract.py`.
- New env var `IMAGE_BINARIES_TENANTS_ALLOWLIST`. New dependency `Pillow` (pinned). Docker image gains `libreoffice-draw` + `fonts-dejavu-core` (≈ +350 MB) for EMF/WMF rasterisation.
```

Under `Changed`: `- Dockerfile: adds LibreOffice Draw headless layer; COPY image_embedder.py.`

---

## 5. `Dockerfile` / `requirements.txt`

`requirements.txt` — append:
```
# P1-IMG-2: deterministic PNG re-encoding + Pillow-native rasterisation.
# Pinned: a Pillow bump can change PNG bytes -> Binary ids -> golden baselines.
Pillow==12.3.0
```

`Dockerfile` — add after the apt layer (keep it a separate layer for caching):
```dockerfile
# P1-IMG-2: LibreOffice Draw headless rasterises EMF/WMF -> PNG.
# Pinned via the Debian release in the base image; a base bump is an IMG-impact change.
RUN apt-get update && \
    apt-get install -y --no-install-recommends libreoffice-draw fonts-dejavu-core && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
```
and next to the other module copies: `COPY image_embedder.py .`

Runtime notes for the converter: invoke `soffice --headless --norestore --nologo -env:UserInstallation=file:///tmp/lo-<correlation_id> --convert-to png --outdir <tmpdir> <files…>`; `subprocess.run(timeout=15)`; always `normalise_png()` the result; delete the temp profile dir in `finally`.

---
## 6. Tests — written first, failing today

Three new files. Copy each verbatim. Run order after copying:

```bash
python3 tests/fixtures/gen_synthetic_smpc_images.py          # writes the fixture (deterministic media bytes)
python3 -m unittest tests.unit.test_image_binaries -v          # 22 FAIL + 2 pass today
python3 -m unittest tests.contract.test_image_contract -v      # 9 tests: 6 FAIL + 3 pass today (needs validator / network like test_publication)
```

Expected outcome on the **current** codebase (verified 2026-09-08 in a sandbox against a stub for the 19 embedder-level tests; the Composition/contract tests are verified by code reading only — run them in the dev environment first):

| Test class | Today | Why |
|---|---|---|
| `EmbedTests`, `RasteriseTests`, `AltTextTests`, `IdempotencyTests` (19) | **FAIL** — `AssertionError: P1-IMG-1 not implemented: image_embedder module missing` | module does not exist |
| `CompositionWiringTests` (3) | **FAIL** — same message (guard in `setUp`) | module does not exist; once it exists, they fail on `create_doc_composition() got an unexpected keyword argument 'embedder'` |
| `LegacyGuardTests` (2) | **pass** — and must keep passing | flag-off path is today's behaviour |
| `ResponseShapeTests` (2) | **pass** today (21 keys); protects against anyone adding a field | — |
| `FeatureOffLegacyTests` (1) | **pass** — must keep passing | — |
| `FeatureOnTests` (6) | **FAIL** — `data:image` still present, 0 `<contained>`, no `IMG-*` rows | tenant flag not read, no embedding |

Green definition: all 33 tests pass, `python3 test_e2e.py tests/fixtures/synthetic_smpc.docx` output unchanged, `tests/fixtures/synthetic_smpc.expected.json` fidelity unchanged, and `validator_cli.jar` reports no new errors on `synthetic_smpc_images.docx` vs `synthetic_smpc.docx`.

### 6.1 `tests/fixtures/gen_synthetic_smpc_images.py`

```python
"""
Deterministic synthetic SmPC fixture WITH embedded images (P1-IMG-1..4).

Produces `tests/fixtures/synthetic_smpc_images.docx`: the same fictional
"Synthex 50 mg" SmPC as `gen_synthetic_smpc.py`, plus four inline pictures
placed so that every P1-IMG code path is exercised exactly once:

  #  | section | format | alt text                         | exercises
  ---+---------+--------+----------------------------------+------------------------------
  1  | 2       | PNG    | present                          | IMG-EMBED (web-safe, alt kept)
  2  | 4.2     | PNG    | ABSENT                           | IMG-ALT-MISSING -> alt="Figure 2"
  3  | 5.1     | TIFF   | present                          | IMG-RASTERISE (TIFF -> PNG)
  4  | 5.2     | PNG    | present, SAME BYTES as #1        | IMG-EMBED dedupe -> same Binary id

All pixels are synthetic geometry (no fonts, no text) so the PNG/TIFF bytes
are byte-identical on every run of this generator on every platform.

Usage:
    python3 tests/fixtures/gen_synthetic_smpc_images.py

Refs:
- FEATURE_SPEC.md §5 P1-IMG-1..4; CLAUDE.md §7.2 (golden corpus), §4.4
  (reproducible runs), §10 #15 (fixture content is intentionally fictional).
"""
from __future__ import annotations

import hashlib
import io
import os
import sys

from docx.shared import Mm
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_synthetic_smpc import build_document  # noqa: E402  (same directory)


# --------------------------------------------------------------------------
# Deterministic synthetic images
# --------------------------------------------------------------------------

def _png_structure() -> bytes:
    """120x60 PNG: a fictional 'chemical structure' made of hexagons/lines."""
    im = Image.new("RGB", (120, 60), "white")
    d = ImageDraw.Draw(im)
    hexagon = [(20, 30), (30, 13), (50, 13), (60, 30), (50, 47), (30, 47)]
    d.polygon(hexagon, outline="black")
    d.line([(60, 30), (80, 30)], fill="black", width=2)
    d.ellipse([(80, 20), (100, 40)], outline="black", width=2)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=False, compress_level=6)
    return buf.getvalue()


def _png_flowchart() -> bytes:
    """160x80 PNG: two boxes and an arrow (a fictional dosing flow)."""
    im = Image.new("RGB", (160, 80), "white")
    d = ImageDraw.Draw(im)
    d.rectangle([(10, 20), (60, 60)], outline="black", width=2)
    d.rectangle([(100, 20), (150, 60)], outline="black", width=2)
    d.line([(60, 40), (100, 40)], fill="black", width=2)
    d.polygon([(100, 40), (92, 35), (92, 45)], fill="black")
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=False, compress_level=6)
    return buf.getvalue()


def _tiff_chart() -> bytes:
    """140x70 uncompressed TIFF: bars (a fictional PK chart). Non-web-safe MIME."""
    im = Image.new("RGB", (140, 70), "white")
    d = ImageDraw.Draw(im)
    for i, h in enumerate((20, 35, 50, 42, 28)):
        x0 = 10 + i * 25
        d.rectangle([(x0, 65 - h), (x0 + 15, 65)], fill="black")
    d.line([(5, 65), (135, 65)], fill="black", width=1)
    buf = io.BytesIO()
    im.save(buf, format="TIFF", compression=None)
    return buf.getvalue()


IMAGES = {
    # key: (bytes, filename, alt_text or None, section heading to attach to)
    "fig1": (_png_structure(), "fig1.png",
             "Chemical structure of synthexine (fictional)", "2."),
    "fig2": (_png_flowchart(), "fig2.png",
             None, "4.2"),
    "fig3": (_tiff_chart(), "fig3.tiff",
             "Mean plasma concentration over time (fictional)", "5.1"),
    "fig4": (_png_structure(), "fig4.png",   # SAME BYTES as fig1 -> dedupe
             "Chemical structure of synthexine, repeated (fictional)", "5.2"),
}


# --------------------------------------------------------------------------
# DOCX assembly
# --------------------------------------------------------------------------

def _find_heading_paragraph(doc, prefix: str):
    """Return the first bold paragraph whose text starts with `prefix`."""
    for p in doc.paragraphs:
        txt = p.text.strip()
        if txt.startswith(prefix) and p.runs and p.runs[0].bold:
            return p
    raise KeyError(f"heading starting with {prefix!r} not found")


def _next_heading_after(doc, para):
    """Return the first bold heading paragraph after `para` (or None)."""
    seen = False
    for p in doc.paragraphs:
        if p._p is para._p:
            seen = True
            continue
        if seen and p.runs and p.runs[0].bold and p.text.strip():
            return p
    return None


def _insert_picture_at_section_end(doc, heading_prefix: str, data: bytes,
                                   filename: str, alt: str | None) -> None:
    heading = _find_heading_paragraph(doc, heading_prefix)
    nxt = _next_heading_after(doc, heading)
    if nxt is None:
        target = doc.add_paragraph()
    else:
        target = nxt.insert_paragraph_before()
    run = target.add_run()
    shape = run.add_picture(io.BytesIO(data), width=Mm(40))
    # python-docx exposes docPr; `descr` is what Word shows as "Alt Text" and
    # what mammoth surfaces as <img alt="...">.
    doc_pr = shape._inline.docPr
    doc_pr.set("name", filename)
    if alt is not None:
        doc_pr.set("descr", alt)
    else:
        # Make sure no alt text sneaks in from the template.
        if "descr" in doc_pr.attrib:
            del doc_pr.attrib["descr"]


def build_document_with_images():
    doc = build_document()
    for key in ("fig1", "fig2", "fig3", "fig4"):
        data, filename, alt, heading = IMAGES[key]
        _insert_picture_at_section_end(doc, heading, data, filename, alt)
    return doc


def main() -> int:
    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, "synthetic_smpc_images.docx")
    doc = build_document_with_images()
    doc.save(out_path)
    print(f"wrote {out_path} ({os.path.getsize(out_path):,} bytes)")
    for key, (data, filename, alt, heading) in IMAGES.items():
        print(f"  {key}: {filename:9s} section {heading:4s} "
              f"sha256={hashlib.sha256(data).hexdigest()[:16]} "
              f"alt={'yes' if alt else 'NO'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### 6.2 `tests/unit/test_image_binaries.py`

```python
"""
Unit tests for P1-IMG-1..4 — images from an uploaded DOCX become contained
FHIR Binary resources referenced from the narrative as <img src="#id"/>.

Written BEFORE the implementation (CLAUDE.md §6 Step 4). Every test in this
file is expected to FAIL on the current codebase for the reasons noted in
SPEC_P1-IMG_IMAGES_2026-09-08.md §6, except the two "legacy guard" tests
which must pass before AND after the change.

Refs: FEATURE_SPEC.md §5 P1-IMG-1..4; CLAUDE.md §5.5 (idempotency), §7.3
(three-input idempotency + no-op safety), §9.3/§9.4 (narrative + mapping rules).

Run:
    python3 -m unittest tests.unit.test_image_binaries -v
"""
from __future__ import annotations

import base64
import hashlib
import io
import os
import re
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# The module under test does not exist yet. Import defensively so a missing
# module produces a *failing assertion with a requirement ID*, not an ERROR.
try:
    import image_embedder as ie  # new module — see spec §3.1
    _IMPORT_ERROR = None
except ImportError as exc:  # pragma: no cover — expected until implemented
    ie = None
    _IMPORT_ERROR = exc

EXT_IMAGE_REFERENCE = "http://ema.europa.eu/fhir/StructureDefinition/ext-epi-image-reference"


# --------------------------------------------------------------------------
# Deterministic sample images (no fonts, no metadata)
# --------------------------------------------------------------------------

def _png_bytes(w: int = 8, h: int = 4) -> bytes:
    from PIL import Image
    im = Image.new("RGB", (w, h), "white")
    for x in range(0, w, 2):
        im.putpixel((x, 0), (0, 0, 0))
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=False, compress_level=6)
    return buf.getvalue()


def _tiff_bytes() -> bytes:
    from PIL import Image
    im = Image.new("RGB", (6, 6), "white")
    im.putpixel((1, 1), (0, 0, 0))
    buf = io.BytesIO()
    im.save(buf, format="TIFF", compression=None)
    return buf.getvalue()


def _data_uri(data: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def _img(data: bytes, mime: str, alt: str | None = None, extra: str = "") -> str:
    alt_attr = f' alt="{alt}"' if alt is not None else ""
    return f'<img src="{_data_uri(data, mime)}"{alt_attr}{extra} />'


def _expected_id(final_bytes: bytes) -> str:
    return "img-" + hashlib.sha256(final_bytes).hexdigest()[:32]


class _Base(unittest.TestCase):
    def setUp(self):
        if ie is None:
            self.fail(
                "P1-IMG-1 not implemented: `image_embedder` module missing "
                f"({_IMPORT_ERROR}). See SPEC_P1-IMG_IMAGES_2026-09-08.md §3.1."
            )


# --------------------------------------------------------------------------
# P1-IMG-1 — data: URI -> contained Binary + <img src="#id">
# --------------------------------------------------------------------------

class EmbedTests(_Base):

    def test_data_uri_is_rewritten_to_fragment_ref(self):
        png = _png_bytes()
        emb = ie.ImageEmbedder()
        out = emb.process(f"<p>Before</p>{_img(png, 'image/png', 'A figure')}<p>After</p>", location="2")
        self.assertNotIn("data:", out, "data: URI must not survive embedding")
        self.assertIn(f'src="#{_expected_id(png)}"', out)
        self.assertEqual(len(emb.binaries), 1)
        b = emb.binaries[0]
        self.assertEqual(b.id, _expected_id(png))
        self.assertEqual(b.content_type, "image/png")
        self.assertEqual(base64.b64decode(b.data_b64), png, "web-safe bytes pass through unchanged")
        self.assertEqual(b.byte_size, len(png))
        self.assertEqual(b.sha256, hashlib.sha256(png).hexdigest())

    def test_binary_id_is_deterministic_and_fhir_id_safe(self):
        png = _png_bytes()
        ids = set()
        for _ in range(3):
            emb = ie.ImageEmbedder()
            emb.process(_img(png, "image/png", "x"), location="2")
            ids.add(emb.binaries[0].id)
        self.assertEqual(len(ids), 1)
        (bid,) = ids
        self.assertRegex(bid, r"^[A-Za-z0-9\-\.]{1,64}$", "FHIR id datatype constraint")
        self.assertTrue(bid.startswith("img-"))

    def test_identical_bytes_dedupe_to_one_binary(self):
        png = _png_bytes()
        emb = ie.ImageEmbedder()
        out = emb.process(_img(png, "image/png", "first") + _img(png, "image/png", "second"), location="5.2")
        self.assertEqual(len(emb.binaries), 1, "byte-identical images share one Binary")
        self.assertEqual(out.count(f'src="#{_expected_id(png)}"'), 2)
        self.assertEqual(sum(1 for a in emb.actions if a.rule == "IMG-EMBED"), 2,
                         "one IMG-EMBED audit entry per <img>, even when deduped")

    def test_binaries_keep_document_order_across_sections(self):
        a, b = _png_bytes(8, 4), _png_bytes(10, 4)
        emb = ie.ImageEmbedder()
        emb.process(_img(a, "image/png", "a"), location="2")
        emb.process(_img(b, "image/png", "b"), location="4.2")
        self.assertEqual([x.id for x in emb.binaries], [_expected_id(a), _expected_id(b)])

    def test_output_img_carries_exactly_src_and_alt(self):
        png = _png_bytes()
        emb = ie.ImageEmbedder()
        out = emb.process(_img(png, "image/png", "kept", extra=' width="300" height="120" style="float:left" class="x"'), location="2")
        tags = re.findall(r"<img\b[^>]*>", out)
        self.assertEqual(len(tags), 1)
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', tags[0]))
        self.assertEqual(set(attrs), {"src", "alt"}, f"unexpected attributes on <img>: {attrs}")
        self.assertTrue(tags[0].endswith("/>"), "XHTML void element must self-close")

    def test_embed_action_has_audit_evidence(self):
        png = _png_bytes()
        emb = ie.ImageEmbedder()
        emb.process(_img(png, "image/png", "x"), location="4.8")
        acts = [a for a in emb.actions if a.rule == "IMG-EMBED"]
        self.assertEqual(len(acts), 1)
        a = acts[0]
        self.assertEqual(a.location, "4.8")
        self.assertIn(_expected_id(png), a.description)
        self.assertIn(hashlib.sha256(png).hexdigest()[:12], a.description)
        self.assertIn("image/png", a.description)


# --------------------------------------------------------------------------
# P1-IMG-2 — non-web-safe MIME types are rasterised to PNG
# --------------------------------------------------------------------------

class RasteriseTests(_Base):

    def test_tiff_is_converted_to_png_binary(self):
        tiff = _tiff_bytes()
        emb = ie.ImageEmbedder()
        out = emb.process(_img(tiff, "image/tiff", "chart"), location="5.1")
        self.assertEqual(len(emb.binaries), 1)
        b = emb.binaries[0]
        self.assertEqual(b.content_type, "image/png")
        png = base64.b64decode(b.data_b64)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"), "payload must be a PNG")
        self.assertEqual(b.id, _expected_id(png), "Binary id is the sha256 of the FINAL (PNG) bytes")
        self.assertEqual(b.source_content_type, "image/tiff")
        self.assertIn(f'src="#{b.id}"', out)

    def test_rasterise_action_records_before_and_after(self):
        tiff = _tiff_bytes()
        emb = ie.ImageEmbedder()
        emb.process(_img(tiff, "image/tiff", "chart"), location="5.1")
        acts = [a for a in emb.actions if a.rule == "IMG-RASTERISE"]
        self.assertEqual(len(acts), 1)
        a = acts[0]
        self.assertIn("image/tiff", a.before_snippet)
        self.assertIn(hashlib.sha256(tiff).hexdigest()[:12], a.before_snippet)
        self.assertIn("image/png", a.after_snippet)
        self.assertIn(emb.binaries[0].sha256[:12], a.after_snippet)

    def test_rasterisation_is_byte_deterministic(self):
        tiff = _tiff_bytes()
        outs = set()
        for _ in range(3):
            emb = ie.ImageEmbedder()
            emb.process(_img(tiff, "image/tiff", "chart"), location="5.1")
            outs.add(emb.binaries[0].sha256)
        self.assertEqual(len(outs), 1, "same input must yield byte-identical PNG (CLAUDE.md §4.4)")

    def test_web_safe_formats_are_not_touched(self):
        png = _png_bytes()
        emb = ie.ImageEmbedder()
        emb.process(_img(png, "image/png", "x"), location="2")
        self.assertFalse(any(a.rule == "IMG-RASTERISE" for a in emb.actions))
        self.assertEqual(base64.b64decode(emb.binaries[0].data_b64), png)

    def test_conversion_failure_preserves_original_and_flags(self):
        tiff = _tiff_bytes()

        def _boom(data: bytes, mime: str) -> bytes:
            raise ie.ImageConversionError("simulated converter outage")

        emb = ie.ImageEmbedder(converter=_boom)
        out = emb.process(_img(tiff, "image/tiff", "chart"), location="5.1")
        self.assertEqual(len(emb.binaries), 1, "never drop regulated content (CLAUDE.md §4.1)")
        b = emb.binaries[0]
        self.assertEqual(b.content_type, "image/tiff", "original preserved with its real MIME type")
        self.assertEqual(base64.b64decode(b.data_b64), tiff)
        self.assertIn(f'src="#{b.id}"', out)
        rules = [a.rule for a in emb.actions]
        self.assertIn("IMG-FORMAT-UNSUPPORTED", rules)
        self.assertNotIn("IMG-RASTERISE", rules)


# --------------------------------------------------------------------------
# P1-IMG-3 — alt text: preserved when present, placeholder + flag when absent
# --------------------------------------------------------------------------

class AltTextTests(_Base):

    def test_existing_alt_is_preserved_verbatim(self):
        png = _png_bytes()
        emb = ie.ImageEmbedder()
        out = emb.process(_img(png, "image/png", "Squeeze bottle to release one drop"), location="6.6")
        self.assertIn('alt="Squeeze bottle to release one drop"', out)
        self.assertFalse(any(a.rule == "IMG-ALT-MISSING" for a in emb.actions))

    def test_missing_alt_gets_placeholder_and_flag(self):
        png = _png_bytes()
        emb = ie.ImageEmbedder()
        out = emb.process(_img(png, "image/png", alt=None), location="4.2")
        self.assertIn('alt="Figure 1"', out)
        acts = [a for a in emb.actions if a.rule == "IMG-ALT-MISSING"]
        self.assertEqual(len(acts), 1)
        self.assertEqual(acts[0].location, "4.2")

    def test_empty_alt_is_treated_as_missing(self):
        png = _png_bytes()
        emb = ie.ImageEmbedder()
        out = emb.process(_img(png, "image/png", alt=""), location="4.2")
        self.assertIn('alt="Figure 1"', out)
        self.assertTrue(any(a.rule == "IMG-ALT-MISSING" for a in emb.actions))

    def test_placeholder_ordinal_counts_every_img_in_document_order(self):
        a, b, c = _png_bytes(8, 4), _png_bytes(10, 4), _png_bytes(12, 4)
        emb = ie.ImageEmbedder()
        emb.process(_img(a, "image/png", "has alt"), location="2")          # figure 1
        out2 = emb.process(_img(b, "image/png", alt=None), location="4.2")  # figure 2
        out3 = emb.process(_img(c, "image/png", alt=None), location="5.1")  # figure 3
        self.assertIn('alt="Figure 2"', out2)
        self.assertIn('alt="Figure 3"', out3)


# --------------------------------------------------------------------------
# CLAUDE.md §5.5 / §7.3 — idempotency and no-op safety
# --------------------------------------------------------------------------

class IdempotencyTests(_Base):

    def _once_twice(self, html: str):
        emb = ie.ImageEmbedder()
        once = emb.process(html, location="t")
        twice = emb.process(once, location="t")
        return once, twice, emb

    def test_idempotent_on_clean_input(self):
        html = "<p>No images here.</p><table><tr><td>x</td></tr></table>"
        once, twice, emb = self._once_twice(html)
        self.assertEqual(once, twice)
        self.assertEqual(once, html, "no-op input returned byte-equal")
        self.assertEqual(emb.binaries, [])
        self.assertEqual(emb.actions, [])

    def test_idempotent_on_already_fixed_input(self):
        png = _png_bytes()
        emb = ie.ImageEmbedder()
        fixed = emb.process(_img(png, "image/png", "x"), location="2")
        n_bin, n_act = len(emb.binaries), len(emb.actions)
        again = emb.process(fixed, location="2")
        self.assertEqual(again, fixed)
        self.assertEqual(len(emb.binaries), n_bin, "re-processing must not add Binaries")
        self.assertEqual(len(emb.actions), n_act, "re-processing must not add audit actions")

    def test_idempotent_on_mixed_input(self):
        png, tiff = _png_bytes(), _tiff_bytes()
        html = (
            "<h2>4.2 Posology</h2><p>Text " + _img(png, "image/png", alt=None) + " more</p>"
            "<ul><li>" + _img(tiff, "image/tiff", "chart") + "</li></ul>"
        )
        once, twice, _ = self._once_twice(html)
        self.assertEqual(once, twice)

    def test_malformed_data_uri_is_left_untouched_and_flagged(self):
        html = '<p><img src="data:image/png;base64,@@not-base64@@" alt="x" /></p>'
        emb = ie.ImageEmbedder()
        out = emb.process(html, location="2")
        self.assertEqual(out, html, "never mangle content we cannot decode")
        self.assertEqual(emb.binaries, [])
        self.assertTrue(any(a.rule == "IMG-FORMAT-UNSUPPORTED" for a in emb.actions))


# --------------------------------------------------------------------------
# P1-IMG-1 / P1-IMG-4 — Composition wiring (contained + imageReference ext)
# --------------------------------------------------------------------------

def _doc_with_images(png: bytes, tiff: bytes) -> dict:
    return {
        "filename": "synthetic.docx",
        "type": "SmPC",
        "sections": [
            {"section_id": "_preface", "title": "", "text": "<p>ANNEX I</p>" + _img(png, "image/png", "logo")},
            {"section_id": "1", "title": "1. NAME OF THE MEDICINAL PRODUCT", "text": "<p>Synthex 50 mg</p>"},
            {"section_id": "2", "title": "2. QUALITATIVE AND QUANTITATIVE COMPOSITION",
             "text": "<p>Each tablet</p>" + _img(png, "image/png", "structure")},
            {"section_id": "4.2", "title": "4.2 Posology", "text": "<p>Dose</p>" + _img(tiff, "image/tiff", alt=None)},
        ],
    }


class CompositionWiringTests(_Base):

    def _build(self, doc, embedder):
        import fhir_mapper as mapper
        try:
            return mapper.create_doc_composition(doc, "urn:uuid:med-prod", "urn:uuid:org", embedder=embedder)
        except TypeError as exc:
            self.fail(f"P1-IMG-1: create_doc_composition does not accept embedder= ({exc})")

    def test_composition_has_contained_binaries_and_image_reference_extensions(self):
        png, tiff = _png_bytes(), _tiff_bytes()
        emb = ie.ImageEmbedder()
        comp = self._build(_doc_with_images(png, tiff), emb)

        contained = comp.contained or []
        self.assertEqual(len(contained), 2, "png deduped across preface+section 2; tiff separate")
        self.assertTrue(all(getattr(r, "resource_type", r.__class__.__name__) == "Binary" for r in contained))
        ids = [r.id for r in contained]
        self.assertEqual(ids, [b.id for b in emb.binaries], "contained order == first-appearance order")

        exts = [e for e in (comp.extension or []) if e.url == EXT_IMAGE_REFERENCE]
        self.assertEqual([e.valueReference.reference for e in exts], [f"#{i}" for i in ids])

        # Narrative: preface -> Composition.text.div; sections -> section.text.div
        self.assertIn(f'src="#{ids[0]}"', comp.text.div)
        all_section_html = " ".join(_walk_section_divs(comp.section))
        self.assertIn(f'src="#{ids[0]}"', all_section_html)
        self.assertIn(f'src="#{ids[1]}"', all_section_html)
        self.assertNotIn("data:", comp.text.div)
        self.assertNotIn("data:", all_section_html)

    def test_xml_serialisation_of_contained_binary(self):
        import fhir_mapper as mapper
        png, tiff = _png_bytes(), _tiff_bytes()
        emb = ie.ImageEmbedder()
        comp = self._build(_doc_with_images(png, tiff), emb)
        xml = mapper.resource_to_xml(comp)
        self.assertIn("<contained><Binary>", xml.replace("\n", "").replace(" <", "<"))
        self.assertIn('<contentType value="image/png"/>', xml)
        self.assertIn("<data value=", xml)
        self.assertIn(f'<extension url="{EXT_IMAGE_REFERENCE}">', xml)
        self.assertIn(f'<reference value="#{emb.binaries[0].id}"/>', xml)
        self.assertNotIn("data:image", xml)
        # FHIR XML element order on a DomainResource: text, contained, extension
        self.assertLess(xml.index("<text>"), xml.index("<contained>"))
        self.assertLess(xml.index("<contained>"), xml.index(f'<extension url="{EXT_IMAGE_REFERENCE}">'))

    def test_generate_bundle_carries_the_same_binaries(self):
        import fhir_mapper as mapper
        png, tiff = _png_bytes(), _tiff_bytes()
        emb = ie.ImageEmbedder()
        doc = _doc_with_images(png, tiff)
        self._build(doc, emb)
        try:
            bundle = mapper.generate_bundle([doc], embedder=emb)
        except TypeError as exc:
            self.fail(f"P1-IMG-1: generate_bundle does not accept embedder= ({exc})")
        comps = [e.resource for e in bundle.entry if e.resource.__class__.__name__ == "Composition"]
        self.assertEqual(len(comps), 1)
        self.assertEqual([r.id for r in comps[0].contained], [b.id for b in emb.binaries])
        self.assertNotIn("data:image", mapper.bundle_to_xml(bundle))


class LegacyGuardTests(unittest.TestCase):
    """Flag OFF path — must pass today and keep passing (CLAUDE.md §5.1, §5.7)."""

    def test_without_embedder_behaviour_is_unchanged(self):
        import fhir_mapper as mapper
        png, tiff = _png_bytes(), _tiff_bytes()
        comp = mapper.create_doc_composition(_doc_with_images(png, tiff), "urn:uuid:med-prod", "urn:uuid:org")
        self.assertFalse(comp.contained, "no contained resources when images feature is off")
        self.assertIn("data:image/png;base64,", " ".join(_walk_section_divs(comp.section)))

    def test_sanitiser_still_passes_img_through(self):
        # The parser-level intermediate (data: URI) stays as-is; embedding is a mapper concern.
        import doc_parser
        html = _img(_png_bytes(), "image/png", "x")
        self.assertEqual(doc_parser._sanitize_html_styles(html), html)


def _walk_section_divs(sections):
    for s in sections or []:
        if s.text is not None and s.text.div:
            yield s.text.div
        yield from _walk_section_divs(s.section)


if __name__ == "__main__":
    unittest.main()
```

### 6.3 `tests/contract/test_image_contract.py`

```python
"""
Contract tests for P1-IMG-1..4 over the public HTTP surface.

The HTTP contract this file protects:
  - The 21-field response shape is unchanged whether the images feature is on
    or off (CLAUDE.md §5.1). No new top-level keys.
  - Feature OFF (tenant not on IMAGE_BINARIES_TENANTS_ALLOWLIST): byte-for-byte
    legacy behaviour — data: URIs stay inline, no contained Binary.
  - Feature ON: `xml` / `bundle_xml` carry contained Binary resources, every
    <img> is `src="#<id>"` with non-empty alt, no data: URIs anywhere in the
    emitted narrative, `fix_log` carries IMG-* audit rows at iteration 0, and
    `source_text` contains no base64 image payload.
  - Same upload twice -> identical Binary ids and payload hashes (CLAUDE.md §4.4).

Uses `tests/fixtures/synthetic_smpc_images.docx` (generated by
`tests/fixtures/gen_synthetic_smpc_images.py`): 4 <img> tags, 3 distinct
images (fig1 == fig4), one without alt text, one TIFF.

Refs: FEATURE_SPEC.md §5 P1-IMG-1..4; CLAUDE.md §5.1, §5.7, §9.1, §9.3.

Run:
    python3 -m unittest tests.contract.test_image_contract -v
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_FIXTURE_PATH = os.path.join(_REPO_ROOT, "tests", "fixtures", "synthetic_smpc_images.docx")
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_IMG_TENANT = "img-tenant"
_OTHER_TENANT = "plain-tenant"

# v2.0.0 baseline response shape — frozen public contract (mirrors test_publication.py).
_BASELINE_FIELDS = frozenset({
    "status", "error_count", "warning_count", "info_count", "summary", "iterations",
    "original_xml", "xml", "issues", "fix_log", "validation_log_json",
    "validation_report_md", "fidelity_score", "fidelity_status", "diff_html",
    "bundle_json", "bundle_xml", "source_text", "doc_type", "sections_count", "css_href",
})

_IMG_TAG = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_CONTAINED_BINARY = re.compile(r"<contained>\s*<Binary>(.*?)</Binary>\s*</contained>", re.DOTALL)


class _ImageContractBase(unittest.TestCase):

    def setUp(self):
        if not os.path.exists(_FIXTURE_PATH):
            self.skipTest(f"fixture not present: {_FIXTURE_PATH} "
                          "(run tests/fixtures/gen_synthetic_smpc_images.py)")
        os.environ["IMAGE_BINARIES_TENANTS_ALLOWLIST"] = _IMG_TENANT
        os.environ.pop("PUBLICATION_TENANTS_ALLOWLIST", None)
        for mod in ("main", "publication_service", "fhir_mapper", "image_embedder"):
            sys.modules.pop(mod, None)
        from fastapi.testclient import TestClient
        import main as main_module
        self.client = TestClient(main_module.app)

    def _post(self, tenant_id: str) -> dict:
        with open(_FIXTURE_PATH, "rb") as fh:
            r = self.client.post(
                "/api/process_stateless",
                files={"file": ("synthetic_smpc_images.docx", fh, _DOCX_MIME)},
                data={"tenant_id": tenant_id},
            )
        if r.status_code == 422:
            self.skipTest("fixture did not pass the SmPC structural gate (P0-2) — regenerate fixture")
        self.assertEqual(r.status_code, 200, r.text[:500])
        return r.json()

    @staticmethod
    def _binaries(xml: str) -> list[dict]:
        out = []
        for m in _CONTAINED_BINARY.finditer(xml):
            body = m.group(1)
            out.append({
                "id": re.search(r'<id value="([^"]+)"', body).group(1),
                "contentType": re.search(r'<contentType value="([^"]+)"', body).group(1),
                "data_sha": hashlib.sha256(re.search(r'<data value="([^"]*)"', body).group(1).encode()).hexdigest(),
            })
        return out


class ResponseShapeTests(_ImageContractBase):

    def test_feature_on_keeps_21_field_shape(self):
        body = self._post(_IMG_TENANT)
        self.assertEqual(set(body.keys()), _BASELINE_FIELDS,
                         "P1-IMG adds NO top-level fields — the manifest lives in the bundle (contained Binary + ext-epi-image-reference)")

    def test_feature_off_keeps_21_field_shape(self):
        body = self._post(_OTHER_TENANT)
        self.assertEqual(set(body.keys()), _BASELINE_FIELDS)


class FeatureOffLegacyTests(_ImageContractBase):
    """Must pass today AND after the change (flag default-off, CLAUDE.md §5.7)."""

    def test_tenant_not_allowlisted_gets_legacy_data_uris(self):
        body = self._post(_OTHER_TENANT)
        self.assertIn("data:image/", body["xml"])
        self.assertNotIn("<contained>", body["xml"])
        self.assertFalse(any(str(f.get("rule", "")).startswith("IMG-") for f in body["fix_log"]))


class FeatureOnTests(_ImageContractBase):

    def test_narrative_images_are_contained_binaries(self):
        body = self._post(_IMG_TENANT)
        for field in ("xml", "bundle_xml"):
            xml = body[field]
            self.assertNotIn("data:image", xml, f"{field}: data: URI leaked into narrative")
            bins = self._binaries(xml)
            self.assertEqual(len(bins), 3, f"{field}: fig1==fig4 dedupes -> 3 Binaries, got {len(bins)}")
            ids = [b["id"] for b in bins]
            self.assertEqual(len(set(ids)), 3, "contained ids unique within the Composition")
            for b in bins:
                self.assertRegex(b["id"], r"^img-[0-9a-f]{32}$")
                self.assertIn(b["contentType"], {"image/png", "image/jpeg", "image/svg+xml"},
                              "only web-safe MIME types after rasterisation")
            self.assertEqual(sum(1 for b in bins if b["contentType"] == "image/png"), 3,
                             "TIFF must have been rasterised to PNG")
            imgs = _IMG_TAG.findall(xml)
            self.assertEqual(len(imgs), 4, f"{field}: 4 <img> tags expected, got {len(imgs)}")
            for tag in imgs:
                attrs = dict(re.findall(r'(\w+)="([^"]*)"', tag))
                self.assertEqual(set(attrs), {"src", "alt"}, tag)
                self.assertIn(attrs["src"].lstrip("#"), ids, f"dangling image ref {attrs['src']}")
                self.assertTrue(attrs["alt"].strip(), f"empty alt on {tag}")
            # Every Binary is declared via the EU imageReference extension, in the same order.
            refs = re.findall(
                r'<extension url="http://ema\.europa\.eu/fhir/StructureDefinition/ext-epi-image-reference">'
                r'\s*<valueReference>\s*<reference value="#([^"]+)"/>', xml)
            self.assertEqual(refs, ids)

    def test_fix_log_has_image_audit_rows_at_iteration_zero(self):
        body = self._post(_IMG_TENANT)
        img_rows = [f for f in body["fix_log"] if str(f.get("rule", "")).startswith("IMG-")]
        by_rule = {}
        for f in img_rows:
            by_rule.setdefault(f["rule"], []).append(f)
        self.assertEqual(len(by_rule.get("IMG-EMBED", [])), 4, by_rule)
        self.assertEqual(len(by_rule.get("IMG-ALT-MISSING", [])), 1, by_rule)
        self.assertEqual(len(by_rule.get("IMG-RASTERISE", [])), 1, by_rule)
        self.assertNotIn("IMG-FORMAT-UNSUPPORTED", by_rule)
        for f in img_rows:
            self.assertEqual(f["iteration"], 0, "mapping-phase actions are logged as iteration 0")
            self.assertEqual(set(f.keys()), {"iteration", "rule", "description", "location"},
                             "same row shape as validator fixes")
            self.assertTrue(f["location"], "location must name the section id")
        # The un-alt'd image sits in section 4.2 of the fixture.
        self.assertEqual(by_rule["IMG-ALT-MISSING"][0]["location"], "4.2")

    def test_source_text_has_no_base64_payload(self):
        body = self._post(_IMG_TENANT)
        self.assertNotIn("data:image", body["source_text"])
        self.assertNotIn(";base64,", body["source_text"])

    def test_original_xml_already_carries_binaries(self):
        # Embedding is a mapping-phase transform: Phase 1 must validate the
        # same Binary-bearing XML that ships (CLAUDE.md §5.3 — no post-hoc rewrite).
        body = self._post(_IMG_TENANT)
        self.assertEqual(len(self._binaries(body["original_xml"])), 3)
        self.assertNotIn("data:image", body["original_xml"])

    def test_same_upload_is_byte_deterministic_for_images(self):
        a = self._binaries(self._post(_IMG_TENANT)["bundle_xml"])
        b = self._binaries(self._post(_IMG_TENANT)["bundle_xml"])
        self.assertEqual(a, b, "Binary ids and payload hashes must not vary run to run")

    def test_fidelity_is_not_degraded_by_images(self):
        # Images contribute zero words to the recall scorer, so the image-bearing
        # fixture must score within rounding of its image-free sibling
        # (CLAUDE.md §5.8 — the reference set never regresses).
        plain_path = os.path.join(_REPO_ROOT, "tests", "fixtures", "synthetic_smpc.docx")
        if not os.path.exists(plain_path):
            self.skipTest("image-free sibling fixture missing")
        with_images = self._post(_IMG_TENANT)
        with open(plain_path, "rb") as fh:
            r = self.client.post("/api/process_stateless",
                                 files={"file": ("synthetic_smpc.docx", fh, _DOCX_MIME)},
                                 data={"tenant_id": _IMG_TENANT})
        self.assertEqual(r.status_code, 200)
        plain = r.json()
        if with_images["fidelity_status"] != "available" or plain["fidelity_status"] != "available":
            self.skipTest("fidelity suppressed by validator errors — not an image concern")
        self.assertAlmostEqual(with_images["fidelity_score"], plain["fidelity_score"], delta=0.5)

if __name__ == "__main__":
    unittest.main()
```

### 6.4 `tests/fixtures/README.md` — append

```markdown
- `synthetic_smpc_images.docx` — generated by `gen_synthetic_smpc_images.py`. Same fictional SmPC plus 4 pictures: PNG+alt (§2), PNG without alt (§4.2), TIFF+alt (§5.1), duplicate of the first PNG (§5.2). Exercises P1-IMG-1..4. Regenerate only via the script; media bytes are byte-deterministic.
- `images/chemdraw_sample.emf`, `images/sample.wmf` — **to be supplied by a design partner** (Open Question 23). Tests skip when absent.
```

---

## 7. Implementation hand-off (paste into the dev session after the spec/test edits are committed)

> Operating under `CLAUDE.md`. Requirement IDs **P1-IMG-1..4** are already in `FEATURE_SPEC.md §5`; the failing tests are `tests/unit/test_image_binaries.py` and `tests/contract/test_image_contract.py`; the fixture is `tests/fixtures/synthetic_smpc_images.docx`. Make them green with the smallest change. Constraints:
>
> 1. New module `image_embedder.py` exposing: `EXT_IMAGE_REFERENCE`, `WEB_SAFE_MIME`, `BINARY_ID_PREFIX = "img-"`, `MAX_IMAGE_BYTES_WARN = 1_048_576`, `ImageConversionError`, dataclasses `ImageAction(rule, location, description, before_snippet="", after_snippet="")` and `BinaryRecord(id, content_type, data_b64, byte_size, sha256, source_content_type)`, functions `binary_id_for(bytes)`, `normalise_png(bytes)`, `to_png(bytes, mime)`, and class `ImageEmbedder(converter=None)` with `.process(html, location) -> str`, `.binaries: list[BinaryRecord]`, `.actions: list[ImageAction]`. Regex-based `<img>` rewrite (the codebase is regex-on-HTML throughout; do not introduce an HTML parser). Output tag is exactly `<img src="#<id>" alt="<alt>"/>`.
> 2. `fhir_mapper.create_doc_composition(doc, med_prod_id, org_id, embedder=None)`: when `embedder` is given, call `embedder.process(text, section_id)` on the preface and on every section **in place** (`sec["text"] = …`) *before* `organize_qrd_sections`, then set `contained=[Binary(id=…, contentType=…, data=…)]` from `embedder.binaries` and `extension=[Extension(url=EXT_IMAGE_REFERENCE, valueReference=Reference(reference=f"#{id}"))…]`. `generate_bundle(doc_list, embedder=None)` passes it through. Check `fhir.resources` accepts base64 `str` for `Binary.data`; if it wants `bytes`, decode once — the XML must end up as `<data value="<base64>"/>`.
> 3. `main.py`: read `IMAGE_BINARIES_TENANTS_ALLOWLIST` next to the publish allowlist; `embedder = mapper.ImageEmbedder() if enabled else None`; pass to both `create_doc_composition` and `generate_bundle`; prepend `{"iteration": 0, "rule", "description", "location"}` rows from `embedder.actions` to `fix_log`. `source_text` is already built *after* `create_doc_composition` — leave that order alone; that is what keeps base64 out of it.
> 4. `to_png`: Pillow first; on `UnidentifiedImageError` and MIME in `{image/x-emf, image/emf, image/x-wmf, image/wmf}` call `_libreoffice_to_png` (soffice headless, private `-env:UserInstallation`, `timeout=15`, then `normalise_png`); anything else raises `ImageConversionError`. Never let a converter exception escape `process` — catch, preserve original, write `IMG-FORMAT-UNSUPPORTED`.
> 5. Do not touch `MAX_VALIDATION_ITERATIONS`, `FIDELITY_TARGET`, `_ALLOWED_CLASS_NAMES`, `_PROFILE_NOT_FOUND_PATTERNS`, the 21 response keys, or the Phase 1 → Phase 2 order.
> 6. Evidence per `CLAUDE.md §8`: CHANGELOG entry (§4 above), §7 traceability rows (§2.4), regenerated `validation_log.json` for `synthetic_smpc_images.docx`, and a `synthetic_smpc_images.expected.json` baseline. Run `validator_cli.jar` on the Binary-bearing bundle and paste the error/warning delta vs the image-free fixture into the PR.
> 7. Spawn a verification subagent on `fhir_mapper.py` + `image_embedder.py` before declaring done (`CLAUDE.md §6` Step 7): idempotency, determinism, no `data:` leakage, XML element order (`text` → `contained` → `extension` → `status`).

---

## 8. Sources

- HL7 ePI IG Tech Style Guide — Images: https://build.fhir.org/ig/HL7/emedicinal-product-info/en/tech-style-guide.html#images
- HL7 ePI IG — Build ePI Type 1 (step 4, Convert images to Base64 Binary): https://build.fhir.org/ig/HL7/emedicinal-product-info/en/build-epi1.html
- HL7 ePI IG — Best Practice (image descriptions, WCAG): https://build.fhir.org/ig/HL7/emedicinal-product-info/best-practice.html
- HL7 ePI IG — `binary-epi` profile definitions: https://build.fhir.org/ig/HL7/emedicinal-product-info/en/StructureDefinition-binary-epi-definitions.html
- HL7 ePI IG v1.0.0 — Steps to create ePI Type 2 (Create Binary resource): https://www.hl7.org/fhir/uv/emedicinal-product-info/steps-to-create-epi2.html
- FHIR R5 Narrative — Image References / data: URLs: https://hl7.org/fhir/narrative.html#id
- EMRN ePI IG home (EU IG, samples, profiles): https://epi.ema.europa.eu/fhirig/
- HL7 Confluence — ePI IG project page (links out to the IG; not renderable via fetch on 2026-09-08): https://confluence.hl7.org/spaces/FHIR/pages/139662361/Electronic+Medicinal+Product+Information+FHIR+Implementation+Guide
- Local: `resources/package/StructureDefinition-EUEpiComposition.json` (`contained` short text), `resources/eu-epi-profiles-1.0.0/StructureDefinition-ext-epi-image-reference.json`, `resources/epi-25-100-sample/English_ePI_Sample_BundleCollection.xml`.

*End of draft.*
