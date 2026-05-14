"""
Deterministic synthetic SmPC fixture generator.

Produces `tests/fixtures/synthetic_smpc.docx`: a fictional Summary of Product
Characteristics for a fictional medicine ("Synthex 50 mg film-coated tablets")
that mirrors the EU QRD template structure closely enough to pass:

  * the P0-2 SmPC structural gate in `main.py` (>= 2 anchor IDs from
    {1, 2, 3, 4, 4.1, 4.2, 4.3, 4.4, 4.8, 5, 6, 6.1}); and
  * the `SmPCStrategy` section detection in `doc_parser.py`.

The fixture is **synthetic** — no real medicine, no real MAH, no real
clinical content. Every value below is fictional or generic, intended only
to exercise the conversion pipeline end-to-end in tests. Do not present any
output rendered from this fixture to a regulator or a clinician.

The generator is deterministic — running it twice produces a byte-identical
.docx (modulo the zip container's internal timestamps, which python-docx
seeds from the current time but does not depend on for any test we run).

Usage:
    python3 tests/fixtures/gen_synthetic_smpc.py

Refs:
- FEATURE_SPEC §5 P0-2 (SmPC structural gate), §8 Q8 (golden corpus)
- CLAUDE.md §7.2 (golden corpus discipline), §10 #15 (never claim domain
  expertise we don't have — this fixture's content is intentionally
  nonsense and is labelled as such throughout)
- EU QRD template (SmPC) — section structure follows the QRD numbering
"""
from __future__ import annotations

import os
import sys

from docx import Document
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT


# Every paragraph below is intentionally fictional. The structure mirrors
# the QRD template; the content is generic placeholder text designed to
# exercise the parser and produce a non-empty narrative for diff and
# fidelity calculations.
_SECTIONS: list[tuple[str, str]] = [
    (
        "1. NAME OF THE MEDICINAL PRODUCT",
        "Synthex 50 mg film-coated tablets",
    ),
    (
        "2. QUALITATIVE AND QUANTITATIVE COMPOSITION",
        "Each film-coated tablet contains 50 mg of synthexum (as synthexum hydrochloride). "
        "For the full list of excipients, see section 6.1.",
    ),
    (
        "3. PHARMACEUTICAL FORM",
        "Film-coated tablet. White to off-white, round, biconvex film-coated tablets "
        "of approximately 8 mm in diameter, debossed with \"SX 50\" on one side and plain on the other.",
    ),
    (
        "4. CLINICAL PARTICULARS",
        "",
    ),
    (
        "4.1 Therapeutic indications",
        "Synthex is indicated for the symptomatic management of a fictional condition "
        "in adults. This is a synthetic test fixture and not a real medicinal indication.",
    ),
    (
        "4.2 Posology and method of administration",
        "Posology: the recommended dose is one Synthex 50 mg tablet taken orally once daily, "
        "with or without food. Method of administration: oral use. The tablet should be "
        "swallowed whole with a sufficient amount of water.",
    ),
    (
        "4.3 Contraindications",
        "Hypersensitivity to the active substance or to any of the excipients listed in section 6.1.",
    ),
    (
        "4.4 Special warnings and precautions for use",
        "This fixture is a synthetic test document. The information shown should not be "
        "used to guide any clinical decision. Patients should be informed accordingly.",
    ),
    (
        "4.5 Interaction with other medicinal products and other forms of interaction",
        "No interaction studies have been performed. As this fixture is synthetic, no real "
        "interactions are described.",
    ),
    (
        "4.6 Fertility, pregnancy and lactation",
        "There are no data from the use of Synthex in pregnant or breastfeeding women, "
        "because Synthex is not a real medicine. This section exists only to exercise the "
        "QRD section structure.",
    ),
    (
        "4.7 Effects on ability to drive and use machines",
        "Synthex has no influence on the ability to drive and use machines because Synthex "
        "is fictional. This statement exists for QRD structural completeness only.",
    ),
    (
        "4.8 Undesirable effects",
        "Summary of the safety profile: no real safety profile exists for this synthetic "
        "fixture. Tabulated list of adverse reactions: not applicable. Reporting of "
        "suspected adverse reactions: as this fixture is synthetic, no reporting is required.",
    ),
    (
        "4.9 Overdose",
        "No cases of overdose have been reported. Synthex is a synthetic test fixture and "
        "has no clinical existence.",
    ),
    (
        "5. PHARMACOLOGICAL PROPERTIES",
        "",
    ),
    (
        "5.1 Pharmacodynamic properties",
        "Pharmacotherapeutic group: fictional therapeutic group, ATC code: X99XX99. "
        "Mechanism of action: not applicable; the active substance is synthetic.",
    ),
    (
        "5.2 Pharmacokinetic properties",
        "Absorption: not applicable. Distribution: not applicable. Biotransformation: not "
        "applicable. Elimination: not applicable. All values are notional for a synthetic fixture.",
    ),
    (
        "5.3 Preclinical safety data",
        "Non-clinical data reveal no special hazard for humans, because this fixture is "
        "synthetic and no non-clinical studies have been performed.",
    ),
    (
        "6. PHARMACEUTICAL PARTICULARS",
        "",
    ),
    (
        "6.1 List of excipients",
        "Tablet core: microcrystalline cellulose, lactose monohydrate, croscarmellose sodium, "
        "magnesium stearate. Film coating: hypromellose, titanium dioxide (E171), macrogol 4000.",
    ),
    (
        "6.2 Incompatibilities",
        "Not applicable.",
    ),
    (
        "6.3 Shelf life",
        "36 months.",
    ),
    (
        "6.4 Special precautions for storage",
        "This medicinal product does not require any special storage conditions.",
    ),
    (
        "6.5 Nature and contents of container",
        "PVC/aluminium blister packs containing 30 or 90 film-coated tablets. Not all pack "
        "sizes may be marketed.",
    ),
    (
        "6.6 Special precautions for disposal and other handling",
        "Any unused medicinal product or waste material should be disposed of in accordance "
        "with local requirements.",
    ),
    (
        "7. MARKETING AUTHORISATION HOLDER",
        "Antigravity Test Fixtures Ltd, 1 Synthetic Way, London EC1A 1AA, United Kingdom.",
    ),
    (
        "8. MARKETING AUTHORISATION NUMBER(S)",
        "EU/1/00/000/001 — 30 tablets.\nEU/1/00/000/002 — 90 tablets.",
    ),
    (
        "9. DATE OF FIRST AUTHORISATION / RENEWAL OF THE AUTHORISATION",
        "Date of first authorisation: 01 January 2026. Date of latest renewal: not applicable.",
    ),
    (
        "10. DATE OF REVISION OF THE TEXT",
        "Detailed information on this medicinal product is available on the website of "
        "Antigravity Test Fixtures.",
    ),
]


def build_document() -> Document:
    doc = Document()

    # Annex I header — many real SmPCs sit inside an Annex I wrapper.
    h = doc.add_paragraph()
    h.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    h.add_run("ANNEX I").bold = True
    doc.add_paragraph()

    sub = doc.add_paragraph()
    sub.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    sub.add_run("SUMMARY OF PRODUCT CHARACTERISTICS").bold = True
    doc.add_paragraph()

    # Black-triangle additional monitoring footer is a common QRD feature
    # but optional; we omit it to keep the fixture minimal.

    for heading, body in _SECTIONS:
        p_h = doc.add_paragraph()
        p_h.add_run(heading).bold = True

        if body:
            for para in body.split("\n"):
                doc.add_paragraph(para)

        doc.add_paragraph()  # blank separator

    return doc


def main() -> int:
    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, "synthetic_smpc.docx")
    doc = build_document()
    doc.save(out_path)
    size = os.path.getsize(out_path)
    print(f"wrote {out_path} ({size:,} bytes)")
    print(f"sections: {len(_SECTIONS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
