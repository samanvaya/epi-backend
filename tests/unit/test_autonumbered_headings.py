"""
Unit tests for P0-3a — QRD section numbers that exist only as Word automatic
numbering (`w:numPr`) are materialised as text before mammoth, so the section
splitter and the P0-2 gate see `1. NAME OF THE MEDICINAL PRODUCT`,
`4.1 Therapeutic indications`, … exactly as for a typed-number document.

Written BEFORE the implementation (CLAUDE.md §6 Step 4).

Refs: FEATURE_SPEC.md §5 P0-3a; CLAUDE.md §5.5 (idempotency), §5.8 (reference
set never regresses).

Run:
    python3 -m unittest tests.unit.test_autonumbered_headings -v
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest
import zipfile

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_FIXTURES = os.path.join(_REPO_ROOT, "tests", "fixtures")
_AUTONUM = os.path.join(_FIXTURES, "synthetic_smpc_autonum.docx")
_TYPED = os.path.join(_FIXTURES, "synthetic_smpc.docx")
_TYPED_IMAGES = os.path.join(_FIXTURES, "synthetic_smpc_images.docx")

try:
    import mammoth  # noqa: F401
    _HAVE_MAMMOTH = True
except ImportError:  # pragma: no cover
    _HAVE_MAMMOTH = False

import doc_parser  # noqa: E402


def _paragraphs(docx_bytes: bytes) -> list[tuple[str, bool]]:
    """(text, has_numPr) for every paragraph, in document order, via python-docx."""
    from docx import Document
    from docx.oxml.ns import qn
    d = Document(io.BytesIO(docx_bytes))
    out = []
    for p in d.paragraphs:
        pPr = p._p.pPr
        numPr = pPr.find(qn("w:numPr")) if pPr is not None else None
        num_id = numPr.find(qn("w:numId")) if numPr is not None else None
        # numId 0 is Word's "no numbering" — a cancelled list item is not numbered.
        has_num = num_id is not None and num_id.get(qn("w:val")) not in (None, "0")
        out.append((p.text, has_num))
    return out


def _read(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


class _Base(unittest.TestCase):
    def setUp(self):
        if not hasattr(doc_parser, "_materialise_qrd_numbering"):
            self.fail("P0-3a not implemented: doc_parser._materialise_qrd_numbering missing "
                      "(FEATURE_SPEC.md §5 P0-3a)")
        for p in (_AUTONUM, _TYPED):
            if not os.path.exists(p):
                self.skipTest(f"fixture missing: {p} (run the generator in tests/fixtures/)")


class MaterialiseTests(_Base):

    def test_qrd_headings_get_their_numbers_as_text(self):
        out = doc_parser._materialise_qrd_numbering(_read(_AUTONUM))
        texts = [t for t, _ in _paragraphs(out)]
        for expected in ("1. NAME OF THE MEDICINAL PRODUCT",
                         "2. QUALITATIVE AND QUANTITATIVE COMPOSITION",
                         "4. CLINICAL PARTICULARS",
                         "4.1 Therapeutic indications",
                         "4.2 Posology and method of administration",
                         "4.8 Undesirable effects",
                         "5.1 Pharmacodynamic properties",
                         "6.1 List of excipients",
                         "10. DATE OF REVISION OF THE TEXT"):
            self.assertIn(expected, texts, f"heading not materialised: {expected!r}")

    def test_materialised_headings_lose_numPr_but_body_list_keeps_it(self):
        out = doc_parser._materialise_qrd_numbering(_read(_AUTONUM))
        paras = dict(_paragraphs(out))
        self.assertFalse(paras["4.1 Therapeutic indications"], "heading must not stay a Word list item")
        self.assertFalse(paras["1. NAME OF THE MEDICINAL PRODUCT"])
        body = [t for t, has in _paragraphs(out) if t.startswith("Take one tablet")]
        self.assertEqual(len(body), 1)
        self.assertTrue(dict(_paragraphs(out))["Take one tablet with a glass of water (fictional instruction)."],
                        "body list must keep its numPr (renders as <ol>)")
        self.assertFalse(any(t.startswith("1. Take one tablet") for t, _ in _paragraphs(out)),
                         "body list must not get literal numbers")

    def test_typed_number_documents_are_untouched(self):
        for path in (_TYPED, _TYPED_IMAGES):
            if not os.path.exists(path):
                continue
            raw = _read(path)
            self.assertEqual(doc_parser._materialise_qrd_numbering(raw), raw,
                             f"pre-pass must be a byte-level no-op on {os.path.basename(path)}")

    def test_idempotent(self):
        once = doc_parser._materialise_qrd_numbering(_read(_AUTONUM))
        twice = doc_parser._materialise_qrd_numbering(once)
        self.assertEqual(once, twice)

    def test_only_document_xml_changes(self):
        raw = _read(_AUTONUM)
        out = doc_parser._materialise_qrd_numbering(raw)
        zin, zout = zipfile.ZipFile(io.BytesIO(raw)), zipfile.ZipFile(io.BytesIO(out))
        self.assertEqual(zin.namelist(), zout.namelist())
        for name in zin.namelist():
            if name != "word/document.xml":
                self.assertEqual(zin.read(name), zout.read(name), f"{name} must be untouched")

    def test_section_ids_match_typed_fixture(self):
        if not _HAVE_MAMMOTH:
            self.skipTest("mammoth not installed in this environment")
        typed = [s["section_id"] for s in doc_parser.parse_document(_TYPED)]
        auto = [s["section_id"] for s in doc_parser.parse_document(_AUTONUM)]
        self.assertEqual(auto, typed)
        anchors = {"1", "2", "3", "4", "4.1", "4.2", "4.3", "4.4", "4.8", "5", "6", "6.1"}
        self.assertGreaterEqual(len(set(auto) & anchors), 2, "P0-2 gate would reject this fixture")

    def test_body_list_renders_as_ol_after_mammoth(self):
        if not _HAVE_MAMMOTH:
            self.skipTest("mammoth not installed in this environment")
        html = doc_parser.read_docx(_AUTONUM)
        self.assertRegex(html, r"<ol>\s*<li>Take one tablet")
        self.assertNotIn("<li>Therapeutic indications", html)


class NumberFormatTests(_Base):

    def test_formats(self):
        f = doc_parser._format_number
        self.assertEqual(f(4, "decimal"), "4")
        self.assertEqual(f(4, "decimalZero"), "04")
        self.assertEqual(f(3, "lowerLetter"), "c")
        self.assertEqual(f(27, "lowerLetter"), "aa")
        self.assertEqual(f(3, "upperLetter"), "C")
        self.assertEqual(f(4, "lowerRoman"), "iv")
        self.assertEqual(f(1994, "upperRoman"), "MCMXCIV")
        self.assertEqual(f(7, "none"), "")


class EdgeCaseTests(_Base):
    """Synthetic document.xml fragments exercising the resolver directly.
    Subclasses of _Base so the implementation guard applies; `_p` is also reused
    by the scale probe in the P0-3a review notes."""

    def _docx(self, document_xml: str, numbering_xml: str, styles_xml: str = "") -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("[Content_Types].xml", "<Types/>")
            z.writestr("word/document.xml", document_xml)
            z.writestr("word/numbering.xml", numbering_xml)
            if styles_xml:
                z.writestr("word/styles.xml", styles_xml)
        return buf.getvalue()

    W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    NUMBERING = (
        '<w:numbering %s>'
        '<w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%%1."/></w:lvl>'
        '<w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%%1.%%2"/></w:lvl></w:abstractNum>'
        '<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/></w:lvl></w:abstractNum>'
        '<w:num w:numId="5"><w:abstractNumId w:val="0"/></w:num>'
        '<w:num w:numId="6"><w:abstractNumId w:val="1"/></w:num>'
        '<w:num w:numId="7"><w:abstractNumId w:val="0"/><w:lvlOverride w:ilvl="0"><w:startOverride w:val="4"/></w:lvlOverride></w:num>'
        '</w:numbering>' % W
    )

    def _p(self, text, num_id=None, ilvl=0, style=None):
        ppr = ""
        if num_id is not None or style:
            ppr = "<w:pPr>"
            if style:
                ppr += f'<w:pStyle w:val="{style}"/>'
            if num_id is not None:
                ppr += f'<w:numPr><w:ilvl w:val="{ilvl}"/><w:numId w:val="{num_id}"/></w:numPr>'
            ppr += "</w:pPr>"
        return f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'

    def _texts(self, out: bytes):
        doc = zipfile.ZipFile(io.BytesIO(out)).read("word/document.xml").decode()
        doc = re.sub(r"<w:del\b[^>]*(?<!/)>.*?</w:del>", "", doc, flags=re.DOTALL)  # deleted (tracked) text is not visible
        return [re.sub(r"<[^>]+>", "", p) for p in re.findall(r"<w:p>.*?</w:p>", doc)]

    def test_levels_reset_when_parent_advances(self):
        doc = f'<w:document {self.W}><w:body>' + \
            self._p("NAME OF THE MEDICINAL PRODUCT", 5, 0) + \
            self._p("QUALITATIVE AND QUANTITATIVE COMPOSITION", 5, 0) + \
            self._p("PHARMACEUTICAL FORM", 5, 0) + \
            self._p("CLINICAL PARTICULARS", 5, 0) + self._p("Therapeutic indications", 5, 1) + \
            self._p("Posology and method of administration", 5, 1) + \
            self._p("PHARMACOLOGICAL PROPERTIES", 5, 0) + self._p("Pharmacodynamic properties", 5, 1) + \
            "</w:body></w:document>"
        out = self._texts(doc_parser._materialise_qrd_numbering(self._docx(doc, self.NUMBERING)))
        self.assertEqual(out[3], "4. CLINICAL PARTICULARS")
        self.assertEqual(out[4], "4.1 Therapeutic indications")
        self.assertEqual(out[5], "4.2 Posology and method of administration")
        self.assertEqual(out[6], "5. PHARMACOLOGICAL PROPERTIES")
        self.assertEqual(out[7], "5.1 Pharmacodynamic properties", "sub-level must reset when the parent advances")

    def test_wrong_position_is_not_forced(self):
        # A heading whose resolved number disagrees with its QRD position is
        # left alone — we never invent a section id (CLAUDE.md §10).
        doc = f'<w:document {self.W}><w:body>' + self._p("CLINICAL PARTICULARS", 5, 0) + "</w:body></w:document>"
        raw = self._docx(doc, self.NUMBERING)
        self.assertEqual(doc_parser._materialise_qrd_numbering(raw), raw)

    def test_bullets_and_already_numbered_text_are_left_alone(self):
        doc = f'<w:document {self.W}><w:body>' + \
            self._p("Therapeutic indications", 6, 0) + \
            self._p("4.1 Therapeutic indications", 5, 1) + \
            "</w:body></w:document>"
        raw = self._docx(doc, self.NUMBERING)
        self.assertEqual(doc_parser._materialise_qrd_numbering(raw), raw)

    def test_start_override_is_honoured(self):
        doc = f'<w:document {self.W}><w:body>' + self._p("CLINICAL PARTICULARS", 7, 0) + "</w:body></w:document>"
        out = self._texts(doc_parser._materialise_qrd_numbering(self._docx(doc, self.NUMBERING)))
        self.assertEqual(out[0], "4. CLINICAL PARTICULARS")

    def test_style_inherited_numbering(self):
        styles = (f'<w:styles {self.W}><w:style w:type="paragraph" w:styleId="H1">'
                  '<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="5"/></w:numPr></w:pPr></w:style></w:styles>')
        doc = f'<w:document {self.W}><w:body>' + self._p("NAME OF THE MEDICINAL PRODUCT", style="H1") + \
            self._p("QUALITATIVE AND QUANTITATIVE COMPOSITION", style="H1") + "</w:body></w:document>"
        out = self._texts(doc_parser._materialise_qrd_numbering(self._docx(doc, self.NUMBERING, styles)))
        self.assertEqual(out, ["1. NAME OF THE MEDICINAL PRODUCT", "2. QUALITATIVE AND QUANTITATIVE COMPOSITION"])

    def test_non_heading_numbered_paragraphs_are_untouched(self):
        doc = f'<w:document {self.W}><w:body>' + self._p("Take one tablet daily", 5, 0) + "</w:body></w:document>"
        raw = self._docx(doc, self.NUMBERING)
        self.assertEqual(doc_parser._materialise_qrd_numbering(raw), raw)

    # -- robustness edge cases (real-world DOCX quirks) -------------------------

    def _smpc(self, *paras):
        return f'<w:document {self.W}><w:body>' + "".join(paras) + "</w:body></w:document>"

    def test_heading_split_across_runs_with_tab_bookmark_and_proofing_marks(self):
        para = ('<w:p><w:pPr><w:pStyle w:val="Heading1"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="5"/></w:numPr></w:pPr>'
                '<w:bookmarkStart w:id="1" w:name="_Toc1"/><w:proofErr w:type="spellStart"/>'
                '<w:r><w:rPr><w:b/></w:rPr><w:t>NAME</w:t></w:r><w:r><w:tab/></w:r>'
                '<w:r><w:t xml:space="preserve"> OF THE </w:t></w:r><w:proofErr w:type="spellEnd"/>'
                '<w:r><w:t>MEDICINAL PRODUCT</w:t></w:r><w:bookmarkEnd w:id="1"/></w:p>')
        out = doc_parser._materialise_qrd_numbering(self._docx(self._smpc(para), self.NUMBERING))
        doc = zipfile.ZipFile(io.BytesIO(out)).read("word/document.xml").decode()
        self.assertIn('<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">1. </w:t></w:r>', doc,
                      "label run must copy the first run's rPr and precede the original runs")
        self.assertIn('<w:numPr><w:ilvl w:val="0"/><w:numId w:val="0"/></w:numPr>', doc,
                      "numbering is cancelled in place (numId 0), not merely removed")
        self.assertIn('<w:bookmarkStart w:id="1" w:name="_Toc1"/>', doc, "everything else preserved verbatim")

    def test_tracked_change_numbering_is_ignored_and_deleted_text_excluded(self):
        # numPr only inside pPrChange (a *removed* numbering) is not live numbering.
        para_a = ('<w:p><w:pPr><w:pPrChange w:id="9"><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="5"/></w:numPr></w:pPr></w:pPrChange></w:pPr>'
                  '<w:r><w:t>NAME OF THE MEDICINAL PRODUCT</w:t></w:r></w:p>')
        # Deleted text must not count as the heading's visible text.
        para_b = self._p("NAME OF THE MEDICINAL PRODUCT", 5, 0).replace(
            "<w:r>", '<w:del w:id="3"><w:r><w:delText>OLD TITLE </w:delText></w:r></w:del><w:r>', 1)
        raw = self._docx(self._smpc(para_a, para_b), self.NUMBERING)
        out = self._texts(doc_parser._materialise_qrd_numbering(raw))
        self.assertEqual(out[0], "NAME OF THE MEDICINAL PRODUCT", "pPrChange numbering must not be applied")
        self.assertTrue(out[1].endswith("1. NAME OF THE MEDICINAL PRODUCT"), out[1])

    def test_paragraph_nested_in_text_box_does_not_break_scanning(self):
        boxed = ('<w:p><w:r><w:pict><v:shape xmlns:v="urn:schemas-microsoft-com:vml"><v:textbox><w:txbxContent>'
                 + self._p("Take one tablet daily", 5, 0) +
                 '</w:txbxContent></v:textbox></v:shape></w:pict></w:r></w:p>')
        doc = self._smpc(self._p("NAME OF THE MEDICINAL PRODUCT", 5, 0), boxed,
                         self._p("QUALITATIVE AND QUANTITATIVE COMPOSITION", 5, 0))
        out = self._texts(doc_parser._materialise_qrd_numbering(self._docx(doc, self.NUMBERING)))
        self.assertIn("1. NAME OF THE MEDICINAL PRODUCT", out)
        # The boxed body paragraph consumed "2."; the next heading is therefore "3." and is
        # NOT forced into position 2 (we never invent a section id).
        self.assertNotIn("2. QUALITATIVE AND QUANTITATIVE COMPOSITION", out)
        self.assertIn("Take one tablet daily", "".join(out))

    def test_lvltext_variants_are_normalised_for_matching(self):
        numbering = self.NUMBERING.replace('w:val="%1."', 'w:val="(%1)"').replace('w:val="%1.%2"', 'w:val="%1.%2."')
        doc = self._smpc(self._p("NAME OF THE MEDICINAL PRODUCT", 5, 0),
                         self._p("QUALITATIVE AND QUANTITATIVE COMPOSITION", 5, 0),
                         self._p("PHARMACEUTICAL FORM", 5, 0), self._p("CLINICAL PARTICULARS", 5, 0),
                         self._p("Therapeutic indications", 5, 1))
        out = self._texts(doc_parser._materialise_qrd_numbering(self._docx(doc, numbering)))
        self.assertEqual(out[0], "1. NAME OF THE MEDICINAL PRODUCT")
        self.assertEqual(out[4], "4.1 Therapeutic indications")

    def test_numid_zero_cancels_style_numbering(self):
        styles = (f'<w:styles {self.W}><w:style w:type="paragraph" w:styleId="H1">'
                  '<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="5"/></w:numPr></w:pPr></w:style></w:styles>')
        doc = self._smpc(self._p("NAME OF THE MEDICINAL PRODUCT", 0, 0, style="H1"))
        raw = self._docx(doc, self.NUMBERING, styles)
        self.assertEqual(doc_parser._materialise_qrd_numbering(raw), raw)

    def test_missing_or_malformed_numbering_part_is_a_noop(self):
        doc = self._smpc(self._p("NAME OF THE MEDICINAL PRODUCT", 5, 0))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("word/document.xml", doc)
        raw = buf.getvalue()
        self.assertEqual(doc_parser._materialise_qrd_numbering(raw), raw)
        broken = self._docx(doc, "<w:numbering><not-closed>")
        self.assertEqual(doc_parser._materialise_qrd_numbering(broken), broken)
        self.assertEqual(doc_parser._materialise_qrd_numbering(b"not a zip at all"), b"not a zip at all")

    def test_non_standard_namespace_prefix_and_bom(self):
        doc = self._smpc(self._p("NAME OF THE MEDICINAL PRODUCT", 5, 0)).replace("w:", "wx:").replace("xmlns:w=", "xmlns:wx=")
        numbering = self.NUMBERING  # numbering.xml keeps the w prefix (parsed by namespace, not prefix)
        raw = self._docx("\ufeff" + doc, numbering)
        out = doc_parser._materialise_qrd_numbering(raw)
        xml = zipfile.ZipFile(io.BytesIO(out)).read("word/document.xml")
        self.assertTrue(xml.startswith(b"\xef\xbb\xbf"), "BOM preserved")
        self.assertIn(b'<wx:t xml:space="preserve">1. </wx:t>', xml)

    def test_typed_number_in_first_run_with_live_numbering_is_left_alone(self):
        doc = self._smpc(self._p("1. NAME OF THE MEDICINAL PRODUCT", 5, 0))
        raw = self._docx(doc, self.NUMBERING)
        self.assertEqual(doc_parser._materialise_qrd_numbering(raw), raw)

    def test_letter_and_none_formats_never_match_qrd(self):
        numbering = self.NUMBERING.replace('<w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/>',
                                           '<w:numFmt w:val="lowerLetter"/><w:lvlText w:val="%1)"/>')
        doc = self._smpc(self._p("NAME OF THE MEDICINAL PRODUCT", 5, 0))
        raw = self._docx(doc, self.NUMBERING.replace(self.NUMBERING, numbering))
        # "a) NAME OF…" is not a QRD heading, but the plain-decimal fallback "1." is → materialised.
        out = self._texts(doc_parser._materialise_qrd_numbering(raw))
        self.assertEqual(out[0], "1. NAME OF THE MEDICINAL PRODUCT")

    def test_counters_shared_across_num_instances_of_one_abstract(self):
        # Two w:num instances of the same abstractNum continue one sequence (Word semantics).
        doc = self._smpc(self._p("NAME OF THE MEDICINAL PRODUCT", 5, 0),
                         self._p("QUALITATIVE AND QUANTITATIVE COMPOSITION", 5, 0).replace('w:val="5"', 'w:val="7"'))
        out = self._texts(doc_parser._materialise_qrd_numbering(self._docx(doc, self.NUMBERING)))
        # numId 7 overrides level 0 to start at 4 → "4. QUALITATIVE…" disagrees with QRD → untouched.
        self.assertEqual(out[0], "1. NAME OF THE MEDICINAL PRODUCT")
        self.assertEqual(out[1], "QUALITATIVE AND QUANTITATIVE COMPOSITION")

    def test_all_other_parts_and_zip_metadata_preserved(self):
        doc = self._smpc(self._p("NAME OF THE MEDICINAL PRODUCT", 5, 0))
        raw = self._docx(doc, self.NUMBERING, f'<w:styles {self.W}/>')
        out = doc_parser._materialise_qrd_numbering(raw)
        zin, zout = zipfile.ZipFile(io.BytesIO(raw)), zipfile.ZipFile(io.BytesIO(out))
        self.assertEqual([i.filename for i in zin.infolist()], [i.filename for i in zout.infolist()])
        for a, b in zip(zin.infolist(), zout.infolist()):
            self.assertEqual((a.compress_type, a.date_time), (b.compress_type, b.date_time), a.filename)
            if a.filename != "word/document.xml":
                self.assertEqual(zin.read(a.filename), zout.read(b.filename))

    # -- findings from the 2026-09-09 adversarial review ---------------------------

    def test_heading_inside_text_box_is_never_edited_and_no_corruption(self):
        # A numbered heading paragraph whose run holds a text box containing another
        # numbered QRD heading: only the outer paragraph is edited; XML stays well-formed.
        inner = self._p("QUALITATIVE AND QUANTITATIVE COMPOSITION", 5, 0)
        outer = ('<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="5"/></w:numPr></w:pPr>'
                 '<w:r><w:t>NAME OF THE MEDICINAL PRODUCT</w:t></w:r>'
                 '<w:r><w:pict><v:shape xmlns:v="urn:schemas-microsoft-com:vml"><v:textbox><w:txbxContent>'
                 + inner + '</w:txbxContent></v:textbox></v:shape></w:pict></w:r></w:p>')
        out = doc_parser._materialise_qrd_numbering(self._docx(self._smpc(outer), self.NUMBERING))
        doc = zipfile.ZipFile(io.BytesIO(out)).read("word/document.xml").decode()
        import xml.etree.ElementTree as ET
        ET.fromstring(doc)  # well-formed
        self.assertIn('>1. </w:t>', doc)
        self.assertNotIn('>2. </w:t>', doc, "nested paragraph must not be edited")
        self.assertTrue(doc.endswith("</w:body></w:document>"), "no bytes dropped after the paragraph")

    def test_mc_fallback_duplicate_does_not_advance_counters(self):
        box = ('<w:p><w:r><mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
               '<mc:Choice Requires="wps"><w:drawing><w:txbxContent>' + self._p("boxed item", 5, 0) + '</w:txbxContent></w:drawing></mc:Choice>'
               '<mc:Fallback><w:pict><w:txbxContent>' + self._p("boxed item", 5, 0) + '</w:txbxContent></w:pict></mc:Fallback>'
               '</mc:AlternateContent></w:r></w:p>')
        doc = self._smpc(self._p("NAME OF THE MEDICINAL PRODUCT", 5, 0), box,
                         self._p("PHARMACEUTICAL FORM", 5, 0))
        doc = doc.replace(f'<w:document {self.W}>', f'<w:document {self.W} xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">')
        out = self._texts(doc_parser._materialise_qrd_numbering(self._docx(doc, self.NUMBERING)))
        # boxed item consumed "2." exactly once → PHARMACEUTICAL FORM is "3." and matches.
        self.assertIn("3. PHARMACEUTICAL FORM", out)

    def test_self_closing_del_in_paragraph_mark_does_not_hide_text(self):
        para = ('<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="5"/></w:numPr><w:rPr><w:del w:id="1" w:author="a"/></w:rPr></w:pPr>'
                '<w:r><w:t xml:space="preserve">NAME OF THE </w:t></w:r>'
                '<w:del w:id="2" w:author="a"><w:r><w:delText>OLD </w:delText></w:r></w:del>'
                '<w:r><w:t>MEDICINAL PRODUCT</w:t></w:r></w:p>')
        out = self._texts(doc_parser._materialise_qrd_numbering(self._docx(self._smpc(para), self.NUMBERING)))
        self.assertEqual(out[0], "1. NAME OF THE MEDICINAL PRODUCT")

    def test_lvloverride_full_level_redefinition_wins(self):
        numbering = self.NUMBERING.replace(
            '<w:num w:numId="7"><w:abstractNumId w:val="0"/><w:lvlOverride w:ilvl="0"><w:startOverride w:val="4"/></w:lvlOverride></w:num>',
            '<w:num w:numId="7"><w:abstractNumId w:val="0"/><w:lvlOverride w:ilvl="0"><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/></w:lvl></w:lvlOverride></w:num>')
        doc = self._smpc(self._p("NAME OF THE MEDICINAL PRODUCT", 7, 0))
        raw = self._docx(doc, numbering)
        self.assertEqual(doc_parser._materialise_qrd_numbering(raw), raw, "bullet-overridden level is not numbered")

    def test_label_rpr_comes_from_first_text_run_not_footnote_reference(self):
        para = ('<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="5"/></w:numPr></w:pPr>'
                '<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteReference w:id="1"/></w:r>'
                '<w:r><w:rPr><w:b/></w:rPr><w:t>NAME OF THE MEDICINAL PRODUCT</w:t></w:r></w:p>')
        out = doc_parser._materialise_qrd_numbering(self._docx(self._smpc(para), self.NUMBERING))
        doc = zipfile.ZipFile(io.BytesIO(out)).read("word/document.xml").decode()
        self.assertIn('<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">1. </w:t></w:r>', doc)
        self.assertNotIn('superscript"/></w:rPr><w:t xml:space="preserve">1. ', doc)

    def test_reprocessing_cannot_promote_a_drifted_body_paragraph(self):
        # PIL headings 1..6 share an abstractNum with a body list. After pass 1 the
        # headings no longer consume counters, so on pass 2 the body item would
        # resolve to "4." and match the PIL pattern — the order guard must refuse it.
        pil_numbering = self.NUMBERING
        doc = self._smpc(self._p("What Synthex is and what it is used for", 5, 0),
                         self._p("What you need to know before you take Synthex", 5, 0),
                         self._p("How to take Synthex", 5, 0),
                         self._p("Possible side effects", 5, 0),
                         self._p("How to store Synthex", 5, 0),
                         self._p("Contents of the pack and other information", 5, 0),
                         self._p("Possible side effects include nausea (body list item)", 5, 0))
        once = doc_parser._materialise_qrd_numbering(self._docx(doc, pil_numbering))
        twice = doc_parser._materialise_qrd_numbering(once)
        self.assertEqual(once, twice, "second pass must be a no-op")
        texts = self._texts(once)
        self.assertEqual(texts[3], "4. Possible side effects")
        self.assertEqual(texts[6], "Possible side effects include nausea (body list item)")

    def test_pil_step_list_item_named_like_a_section_is_not_promoted(self):
        # Inside PIL section 3, a numbered step list: item 5 happens to read like the
        # section-5 heading. PIL sections must succeed strictly (3 → 4), so it is refused.
        doc = self._smpc(self._p("What Synthex is and what it is used for", 5, 0),
                         self._p("What you need to know before you take Synthex", 5, 0),
                         self._p("How to take Synthex", 5, 0),
                         self._p("Wash your hands", 7, 0), self._p("How to store the pen after use", 7, 0))
        numbering = self.NUMBERING.replace('<w:startOverride w:val="4"/>', '<w:startOverride w:val="4"/>')
        out = self._texts(doc_parser._materialise_qrd_numbering(self._docx(doc, numbering)))
        self.assertEqual(out[2], "3. How to take Synthex")
        self.assertEqual(out[4], "How to store the pen after use")

    def test_zip_comment_preserved(self):
        doc = self._smpc(self._p("NAME OF THE MEDICINAL PRODUCT", 5, 0))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("word/document.xml", doc)
            z.writestr("word/numbering.xml", self.NUMBERING)
            z.comment = b"hello"
        out = doc_parser._materialise_qrd_numbering(buf.getvalue())
        self.assertEqual(zipfile.ZipFile(io.BytesIO(out)).comment, b"hello")


if __name__ == "__main__":
    unittest.main()
