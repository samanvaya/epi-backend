"""
Deterministic synthetic SmPC fixture with UNDERLINED runs (P0-3b).

Produces `tests/fixtures/synthetic_smpc_underline.docx`: the same fictional
"Synthex 50 mg" SmPC as `gen_synthetic_smpc.py`, plus, in section 4.4, one
paragraph with an underlined run and one with a run in Word's built-in
"Hyperlink"-style formatting (underline only — no URL). Before P0-3b these
produced `<u>` in the narrative, which the HL7 validator rejects (`txt-1`).

Usage:
    python3 tests/fixtures/gen_synthetic_smpc_underline.py

Refs: FEATURE_SPEC.md §5 P0-3b; CLAUDE.md §9.3, §10 #5 (SME sign-off
2026-09-10), §10 #15 (fixture content is intentionally fictional).
"""
from __future__ import annotations

import os
import sys

from docx import Document

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_synthetic_smpc import build_document  # noqa: E402

UNDERLINED_TEXT = "must be read before use (fictional underlined warning)"
PLAIN_TAIL = " and kept with the pack."


def build_document_underline() -> Document:
    doc = build_document()
    # Find the 4.4 heading and insert after its first body paragraph.
    paras = doc.paragraphs
    idx = next(i for i, p in enumerate(paras) if p.text.strip().startswith("4.4 Special warnings"))
    target = paras[idx + 1]
    new_p = target.insert_paragraph_before("")  # placeholder, moved below
    # python-docx has no insert_after; move the new paragraph after `target`.
    target._p.addnext(new_p._p)
    r = new_p.add_run("This warning ")
    r2 = new_p.add_run(UNDERLINED_TEXT)
    r2.font.underline = True
    new_p.add_run(PLAIN_TAIL)
    return doc


def main() -> int:
    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, "synthetic_smpc_underline.docx")
    build_document_underline().save(out_path)
    print(f"wrote {out_path} ({os.path.getsize(out_path):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
