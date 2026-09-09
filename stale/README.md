# stale/ — archived material

Moved here on 2026-09-08 (Syo's instruction, session P1-IMG). Nothing in this folder is imported, built, tested or deployed. Files are kept — not deleted — so history stays reviewable (CLAUDE.md §10 #2, §9.7). Git history is preserved through the move (`git log --follow`).

| File (now in `stale/`) | Original path | Group | Last modified · size | Why it is stale |
|---|---|---|---|---|
| `debug_bundle.xml` | `debug_bundle.xml` | Debug artefact | 2026-03-24 · 51,105 B | Hand-captured Composition XML from the 2026-03-24 debugging session; superseded by the pipeline's original_xml / validation_log.json. |
| `debug_bundle_fixed.xml` | `debug_bundle_fixed.xml` | Debug artefact | 2026-03-24 · 52,219 B | Post-fix variant of debug_bundle.xml from the same session. |
| `debug_response.json` | `debug_response.json` | Debug artefact | 2026-03-24 · 255,958 B | Raw API response dump from 2026-03-24; response shape has since been frozen and is covered by tests/contract. |
| `bundle.xml` | `bundle.xml` | Debug artefact | 2026-03-24 · 4 B | 4-byte placeholder left by an early run. |
| `tiny_bundle.xml` | `tiny_bundle.xml` | Debug artefact | 2026-03-24 · 72 B | 72-byte minimal bundle used for early validator smoke tests. |
| `test.pdf` | `test.pdf` | Debug artefact | 2026-03-30 · 10 B | 10-byte placeholder; not a real PDF. |
| `specimen_test.txt` | `specimen_test.txt` | Debug artefact | 2026-03-30 · 109 B | Scratch note from 2026-03-30 upload testing. |
| `test_joey.py` | `test_joey.py` | Debug artefact | 2026-03-30 · 1,587 B | Ad-hoc upload script from 2026-03-30; replaced by test_e2e.py and tests/. |
| `test_upload.py` | `test_upload.py` | Debug artefact | 2026-03-30 · 490 B | Ad-hoc upload script from 2026-03-30; replaced by test_e2e.py and tests/. |
| `main_HF.py` | `main_HF.py` | HuggingFace deploy variant | 2026-03-29 · 7,033 B | Alternative FastAPI entry point for a HuggingFace Space; the Render deployment (main.py / Dockerfile) is the live one. |
| `Dockerfile_HF` | `Dockerfile_HF` | HuggingFace deploy variant | 2026-03-29 · 1,142 B | HuggingFace Space image; superseded by Dockerfile. |
| `requirements_HF.txt` | `requirements_HF.txt` | HuggingFace deploy variant | 2026-03-29 · 154 B | Dependency list for the HuggingFace variant. |
| `Dockerfile_ghcr` | `Dockerfile_ghcr` | HuggingFace deploy variant | 2026-03-29 · 45 B | 45-byte GHCR pointer file for the HuggingFace variant. |
| `deploy-hf.yml` | `.github/workflows/deploy-hf.yml` | HuggingFace deploy variant | 2026-03-29 · 1,142 B | GitHub Actions workflow that built `Dockerfile_HF` to GHCR; moved with the HF files so a manual dispatch cannot run against a missing Dockerfile. |

Kept in the root on purpose: `valid_test.docx` (golden-corpus reference, CLAUDE.md §7.2), `validation_log.json` (regulated evidence record), `DRIFT_REPORT_*.md` (audit history), `COWORK_PROJECT_PROMPT.md`.
