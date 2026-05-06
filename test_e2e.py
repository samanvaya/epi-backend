"""
End-to-end local test — mirrors the /api/process_stateless pipeline exactly.
Usage: python3 test_e2e.py <path_to_docx_or_pdf>
"""
import sys
import os
import re
import json
import time
from dataclasses import asdict

# Add the backend dir to path so imports resolve
sys.path.insert(0, os.path.dirname(__file__))

import doc_parser as parser
import fhir_mapper as mapper
import fhir_validator as validator
import diff_engine

def run(file_path: str):
    t0 = time.time()
    filename = os.path.basename(file_path)
    print(f"\n{'='*60}")
    print(f"  ePI E2E Test: {filename}")
    print(f"{'='*60}\n")

    # ── Step 1: Parse ──────────────────────────────────────────
    print("Step 1 — Parsing document...")
    sections = parser.parse_document(file_path, doc_type="Auto")
    if file_path.lower().endswith(".pdf"):
        raw_html = parser.read_pdf(file_path)
    else:
        raw_html = parser.read_docx(file_path)
    doc_type = parser.DocumentFactory.detect_type(raw_html)
    print(f"  Detected type : {doc_type}")
    print(f"  Total sections: {len(sections)}")
    for s in sections:
        print(f"    [{s['section_id']:15s}] {s['title'][:60]}  ({len(s['text'])} chars)")

    # ── Step 2: Map to FHIR ────────────────────────────────────
    print("\nStep 2 — Mapping to FHIR Composition XML...")
    doc_obj = {"filename": filename, "type": doc_type, "sections": sections}
    comp = mapper.create_doc_composition(doc_obj, "urn:uuid:med-prod", "urn:uuid:org")
    original_xml = mapper.resource_to_xml(comp)
    print(f"  Original XML  : {len(original_xml):,} bytes")

    # ── Step 3: Build source_text (same logic as main.py) ──────
    print("\nStep 3 — Building source_text for fidelity scoring...")
    _NON_SMPC_IDS = {'labelling', 'annex_i', 'annex_ii', 'annex_iii'}
    source_parts = []
    seen_ids: set = set()
    skipped = []
    for s in sections:
        sid = s.get('section_id', '')
        if sid == '_preface':
            skipped.append(f"_preface (metadata)")
            continue
        if sid in _NON_SMPC_IDS:
            skipped.append(f"{sid} (non-SmPC)")
            continue
        if sid in seen_ids:
            skipped.append(f"{sid} (duplicate)")
            continue
        seen_ids.add(sid)
        title = s.get('title', '').strip()
        text  = s.get('text',  '').strip()
        text_no_tags = re.sub(r'^\s*(<[^>]+>)+\s*', '', text)
        if title and (text.lower().startswith(title.lower())
                      or text_no_tags.lower().startswith(title.lower())):
            source_parts.append(text)
        else:
            source_parts.append(f"{title} {text}" if title else text)
    source_text = " ".join(source_parts)

    def _words(t):
        return re.sub(r'<[^>]+>', ' ', t).split()
    print(f"  Source words  : {len(_words(source_text))}")
    if skipped:
        print(f"  Skipped       : {', '.join(skipped)}")

    # ── Step 4: Validation + FidelityFixer pipeline ────────────
    print("\nStep 4 — Running FHIR validation + fidelity pipeline...")
    project_dir = os.path.dirname(os.path.abspath(__file__))
    fixed_xml, val_log, summary, fidelity_score = validator.run_validation_pipeline(
        original_xml,
        project_dir=project_dir,
        source_text=source_text,
    )

    last_run  = val_log.runs[-1] if val_log.runs else None
    first_run = val_log.runs[0]  if val_log.runs else None
    error_count   = last_run.error_count   if last_run else 0
    warning_count = last_run.warning_count if last_run else 0
    info_count    = last_run.info_count    if last_run else 0
    iterations    = len(val_log.runs)

    # ── Step 5: Build bundle ───────────────────────────────────
    print("\nStep 5 — Generating FHIR Bundle (JSON + XML)...")
    bundle      = mapper.generate_bundle([doc_obj])
    bundle_json = mapper.bundle_to_json(bundle)
    bundle_xml  = mapper.bundle_to_xml(bundle)
    print(f"  Bundle JSON   : {len(bundle_json):,} bytes")
    print(f"  Bundle XML    : {len(bundle_xml):,} bytes")

    # ── Step 6: Diff ───────────────────────────────────────────
    try:
        diff_html = diff_engine.generate_html_diff(source_text, fixed_xml)
    except Exception:
        diff_html = ""

    # ── Results ────────────────────────────────────────────────
    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  RESULTS")
    print(f"{'='*60}")

    if error_count == 0:
        status = "✅ VALIDATED"
    elif first_run and error_count < first_run.error_count:
        status = "⚠️  PARTIALLY FIXED"
    else:
        status = "❌ ERRORS REMAIN"

    print(f"  Status        : {status}")
    print(f"  Errors        : {error_count}")
    print(f"  Warnings      : {warning_count}")
    print(f"  Info          : {info_count}")
    print(f"  Val iterations: {iterations}")
    print(f"  Summary       : {summary}")
    print(f"  Fixed XML     : {len(fixed_xml):,} bytes")
    print(f"\n  ★ FIDELITY SCORE: {fidelity_score}%")
    print(f"\n  Elapsed       : {elapsed:.1f}s")

    # Show per-iteration fidelity if FidelityFixer ran
    print(f"\n  Validation runs:")
    for run in val_log.runs:
        fixes = f"  {len(run.fixes_applied)} fix(es)" if run.fixes_applied else ""
        print(f"    Iter {run.iteration}: {run.error_count}E {run.warning_count}W {run.info_count}I{fixes}")

    # Detailed word-level breakdown (same as diagnostic)
    print(f"\n  Fidelity detail:")
    import difflib
    section_xml = re.sub(r'<text\b[^>]*>.*?</text>', '', fixed_xml, count=1, flags=re.DOTALL|re.IGNORECASE)
    def _strip(t):
        t = re.sub(r'<[^>]+>', ' ', t)
        t = re.sub(r'&\w+;', ' ', t)
        return t.lower().split()
    s_words = _strip(source_text)
    t_words = _strip(section_xml)
    matcher = difflib.SequenceMatcher(None, s_words, t_words, autojunk=False)
    matched = sum(b.size for b in matcher.get_matching_blocks())
    missing_words = [w for w in s_words if w not in set(t_words)]
    print(f"    Source words : {len(s_words)}")
    print(f"    Target words : {len(t_words)}")
    print(f"    Matched      : {matched}")
    print(f"    Recall score : {min(100.0, round(matched/max(len(s_words),1)*100,1))}%")
    if missing_words[:20]:
        print(f"    Sample missing words: {missing_words[:20]}")

    print(f"\n{'='*60}\n")
    return fidelity_score


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Default to the Joenja test file
        default = os.path.expanduser("~/Downloads/Joenja_QRD_Final_Template_Sachin-v2.docx")
        if os.path.exists(default):
            run(default)
        else:
            print("Usage: python3 test_e2e.py <file.docx>")
            sys.exit(1)
    else:
        run(sys.argv[1])
