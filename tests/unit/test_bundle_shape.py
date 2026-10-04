"""
Unit tests for P0-4a — nested document Bundles (EMA sample EPI-25-100 shape).

Written BEFORE the implementation (CLAUDE.md §6 Step 4).

Run:
    python3 -m unittest tests.unit.test_bundle_shape -v
"""
from __future__ import annotations

import json
import os
import re
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import fhir_mapper as mapper  # noqa: E402

EU_BUNDLE_PROFILE = "http://ema.europa.eu/fhir/StructureDefinition/EUEpiBundle"


def _doc(name="synthetic.docx"):
    return {
        "filename": name, "type": "SmPC",
        "sections": [
            {"section_id": "1", "title": "1. NAME OF THE MEDICINAL PRODUCT", "text": "<p>Synthex 50 mg</p>"},
            {"section_id": "4", "title": "4. CLINICAL PARTICULARS", "text": ""},
            {"section_id": "4.1", "title": "4.1 Therapeutic indications", "text": "<p>Fictional.</p>"},
        ],
    }


def _as_json(resource) -> dict:
    return json.loads(mapper.resource_to_json(resource))


def _mask(s: str) -> str:
    s = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "UUID", s)
    return re.sub(r"\d{4}-\d{2}-\d{2}T[0-9:.+]+", "TS", s)


class _Base(unittest.TestCase):
    def setUp(self):
        import inspect
        if "nested_document_bundles" not in inspect.signature(mapper.generate_bundle).parameters:
            self.fail("P0-4a not implemented: generate_bundle lacks nested_document_bundles= (FEATURE_SPEC §5 P0-4a)")


class NestedShapeTests(_Base):

    def test_outer_collection_list_first_inner_document_per_composition(self):
        b = _as_json(mapper.generate_bundle([_doc("a.docx"), _doc("b.docx")], nested_document_bundles=True))
        self.assertEqual(b["type"], "collection")
        self.assertNotIn("meta", b, "EUEpiBundle is a document profile; the outer collection carries none (EPI-25-100)")
        entries = b["entry"]
        self.assertEqual(entries[0]["resource"]["resourceType"], "List")
        inner = [e for e in entries if e["resource"]["resourceType"] == "Bundle"]
        self.assertEqual(len(inner), 2, "one inner Bundle per Composition")
        self.assertFalse(any(e["resource"]["resourceType"] == "Composition" for e in entries),
                         "Compositions must not be direct entries of the outer collection")
        for ib in inner:
            r = ib["resource"]
            self.assertEqual(r["type"], "document")
            self.assertIn(EU_BUNDLE_PROFILE, r["meta"]["profile"])
            self.assertEqual(r["identifier"]["value"], r["id"])
            self.assertTrue(r.get("timestamp"))
            self.assertEqual(r["entry"][0]["resource"]["resourceType"], "Composition")
            self.assertEqual(ib["fullUrl"], f"urn:uuid:{r['id']}")
            self.assertTrue(r["entry"][0]["fullUrl"].startswith("urn:uuid:"))

    def test_list_items_point_at_the_compositions(self):
        b = _as_json(mapper.generate_bundle([_doc("a.docx"), _doc("b.docx")], nested_document_bundles=True))
        lst = b["entry"][0]["resource"]
        refs = [e["item"]["reference"] for e in lst["entry"]]
        comp_urls = [e["resource"]["entry"][0]["fullUrl"] for e in b["entry"] if e["resource"]["resourceType"] == "Bundle"]
        self.assertEqual(refs, comp_urls)

    def test_outer_is_list_plus_documents_and_placeholders_ride_inside(self):
        b = _as_json(mapper.generate_bundle([_doc()], nested_document_bundles=True))
        types = [e["resource"]["resourceType"] for e in b["entry"]]
        self.assertEqual(types, ["List", "Bundle"])
        inner = b["entry"][1]["resource"]
        self.assertEqual([e["resource"]["resourceType"] for e in inner["entry"]],
                         ["Composition", "Organization", "MedicinalProductDefinition"])
        # Composition.author / .subject resolve INSIDE the document Bundle.
        comp = inner["entry"][0]["resource"]
        inner_urls = {e["fullUrl"] for e in inner["entry"]}
        self.assertIn(comp["author"][0]["reference"], inner_urls)
        self.assertIn(comp["subject"][0]["reference"], inner_urls)

    def test_inner_bundle_id_equals_composition_id_so_list_refs_are_top_level(self):
        b = _as_json(mapper.generate_bundle([_doc()], nested_document_bundles=True))
        inner_entry = b["entry"][1]
        comp = inner_entry["resource"]["entry"][0]["resource"]
        self.assertEqual(inner_entry["resource"]["id"], comp["id"])
        self.assertEqual(inner_entry["fullUrl"], f"urn:uuid:{comp['id']}")
        self.assertEqual(b["entry"][0]["resource"]["entry"][0]["item"]["reference"], inner_entry["fullUrl"])

    def test_contained_binaries_stay_on_the_composition(self):
        import base64, io
        from PIL import Image
        import image_embedder as ie
        im = Image.new("RGB", (4, 4), "white"); buf = io.BytesIO(); im.save(buf, format="PNG")
        png = buf.getvalue()
        d = _doc()
        d["sections"][2]["text"] += f'<img src="data:image/png;base64,{base64.b64encode(png).decode()}" alt="x"/>'
        emb = ie.ImageEmbedder()
        b = _as_json(mapper.generate_bundle([d], embedder=emb, nested_document_bundles=True))
        inner = [e for e in b["entry"] if e["resource"]["resourceType"] == "Bundle"][0]["resource"]
        comp = inner["entry"][0]["resource"]
        self.assertEqual([c["resourceType"] for c in comp.get("contained", [])], ["Binary"])
        flat = json.dumps(b)
        self.assertEqual(flat.count('"resourceType": "Binary"'), 1, "Binary only as a contained resource")

    def test_xml_nests_bundle_inside_entry_resource(self):
        xml = mapper.bundle_to_xml(mapper.generate_bundle([_doc()], nested_document_bundles=True))
        squashed = re.sub(r">\s+<", "><", xml)
        # Bundle.entry is fullUrl then resource (as in EPI-25-100).
        self.assertRegex(squashed, r'<entry><fullUrl value="urn:uuid:[^"]+"/><resource><Bundle>')
        self.assertIn('<type value="document"/>', squashed)
        self.assertRegex(squashed, r'<resource><Bundle>.*?<resource><Composition>', "Composition inside the inner Bundle")
        self.assertEqual(squashed.count("<Composition>"), 1)

    def test_flag_off_is_unchanged(self):
        # Same shape as today: List, Organization, MPD, Composition — no inner Bundles.
        b = _as_json(mapper.generate_bundle([_doc()]))
        self.assertEqual([e["resource"]["resourceType"] for e in b["entry"]],
                         ["List", "Organization", "MedicinalProductDefinition", "Composition"])
        b2 = _as_json(mapper.generate_bundle([_doc()], nested_document_bundles=False))
        self.assertEqual(_mask(json.dumps(b, sort_keys=True)), _mask(json.dumps(b2, sort_keys=True)))


if __name__ == "__main__":
    unittest.main()
