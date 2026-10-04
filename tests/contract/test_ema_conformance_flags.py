"""
Contract tests for P0-4a (nested document Bundles) and P0-8a (table borders
via CSS) over the public HTTP surface. Both are per-tenant flags; flag-off
output must be byte-identical to v2.0.0 modulo UUIDs / timestamps.

Refs: FEATURE_SPEC.md §5 P0-4a, P0-8a; CLAUDE.md §5.1, §5.7, §9.4 (v1.2).

Run:
    python3 -m unittest tests.contract.test_ema_conformance_flags -v
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

_FIXTURE = os.path.join(_REPO_ROOT, "tests", "fixtures", "synthetic_smpc_table.docx")
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_NESTED_TENANT, _CSS_TENANT, _PLAIN = "nested-tenant", "css-tenant", "plain-tenant"
_BASELINE_FIELDS = frozenset({
    "status", "error_count", "warning_count", "info_count", "summary", "iterations",
    "original_xml", "xml", "issues", "fix_log", "validation_log_json",
    "validation_report_md", "fidelity_score", "fidelity_status", "diff_html",
    "bundle_json", "bundle_xml", "source_text", "doc_type", "sections_count", "css_href",
})


class _Base(unittest.TestCase):
    def setUp(self):
        if not os.path.exists(_FIXTURE):
            self.skipTest("fixture missing")
        for var, val in (("NESTED_DOCUMENT_BUNDLE_TENANTS_ALLOWLIST", _NESTED_TENANT),
                         ("CSS_TABLE_BORDERS_TENANTS_ALLOWLIST", _CSS_TENANT)):
            prev = os.environ.get(var)
            os.environ[var] = val
            self.addCleanup(lambda v=var, p=prev: os.environ.pop(v, None) if p is None else os.environ.__setitem__(v, p))
        for mod in ("main", "feature_flags", "fhir_mapper", "fhir_validator"):
            sys.modules.pop(mod, None)
        from fastapi.testclient import TestClient
        import main as main_module
        self.client = TestClient(main_module.app)

    def _post(self, tenant):
        with open(_FIXTURE, "rb") as fh:
            r = self.client.post("/api/process_stateless",
                                 files={"file": ("synthetic_smpc_table.docx", fh, _DOCX_MIME)},
                                 data={"tenant_id": tenant})
        self.assertEqual(r.status_code, 200, r.text[:400])
        return r.json()


class NestedBundleFlagTests(_Base):

    def test_flag_on_bundle_is_nested_and_shape_is_21_fields(self):
        body = self._post(_NESTED_TENANT)
        self.assertEqual(set(body.keys()), _BASELINE_FIELDS)
        b = json.loads(body["bundle_json"])
        types = [e["resource"]["resourceType"] for e in b["entry"]]
        self.assertEqual(types, ["List", "Bundle"], "outer = List + one document Bundle (EPI-25-100 shape)")
        inner = next(e["resource"] for e in b["entry"] if e["resource"]["resourceType"] == "Bundle")
        self.assertEqual(inner["type"], "document")
        self.assertEqual(inner["entry"][0]["resource"]["resourceType"], "Composition")
        squashed = re.sub(r">\s+<", "><", body["bundle_xml"])
        self.assertRegex(squashed, r'<entry><fullUrl value="urn:uuid:[^"]+"/><resource><Bundle>')
        # The validated Composition XML is untouched by the bundle flag.
        self.assertNotIn("<Bundle", body["xml"])

    def test_flag_off_bundle_is_flat(self):
        b = json.loads(self._post(_PLAIN)["bundle_json"])
        types = [e["resource"]["resourceType"] for e in b["entry"]]
        self.assertEqual(types, ["List", "Organization", "MedicinalProductDefinition", "Composition"])


class CssTableBordersFlagTests(_Base):

    def test_flag_on_no_border_injection_anywhere(self):
        body = self._post(_CSS_TENANT)
        self.assertEqual(set(body.keys()), _BASELINE_FIELDS)
        self.assertIn("<table", body["xml"], "fixture must contain a table")
        for field in ("original_xml", "xml", "bundle_xml"):
            self.assertNotIn('border="1"', body[field], field)
            self.assertNotIn("border-collapse", body[field], field)
        self.assertFalse(any(f["rule"] == "UI_FORMAT_TABLE_BORDERS" for f in body["fix_log"]))

    def test_flag_off_borders_still_injected(self):
        body = self._post(_PLAIN)
        self.assertIn("<table", body["xml"], "fixture must contain a table")
        self.assertIn('border="1"', body["xml"])


if __name__ == "__main__":
    unittest.main()
