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
        # Whitespace-agnostic: the serialiser pretty-prints with tabs/newlines.
        self.assertIn("<contained><Binary>", re.sub(r">\s+<", "><", xml))
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
