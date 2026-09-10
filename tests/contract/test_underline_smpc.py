"""
Contract test for P0-3b over the public HTTP surface: an SmPC with underlined
text validates without the `Invalid element name in the XHTML ('u')` / `txt-1`
findings, the underline is expressed as EMA does, and the 21-field shape holds.

Refs: FEATURE_SPEC.md §5 P0-3b; CLAUDE.md §5.1, §9.3.

Run:
    python3 -m unittest tests.contract.test_underline_smpc -v
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_FIXTURE = os.path.join(_REPO_ROOT, "tests", "fixtures", "synthetic_smpc_underline.docx")
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_BASELINE_FIELDS = frozenset({
    "status", "error_count", "warning_count", "info_count", "summary", "iterations",
    "original_xml", "xml", "issues", "fix_log", "validation_log_json",
    "validation_report_md", "fidelity_score", "fidelity_status", "diff_html",
    "bundle_json", "bundle_xml", "source_text", "doc_type", "sections_count", "css_href",
})


class UnderlineSmpcTests(unittest.TestCase):

    def setUp(self):
        if not os.path.exists(_FIXTURE):
            self.skipTest(f"fixture missing: {_FIXTURE}")
        from fastapi.testclient import TestClient
        import main as main_module
        self.client = TestClient(main_module.app)
        with open(_FIXTURE, "rb") as fh:
            r = self.client.post("/api/process_stateless",
                                 files={"file": ("synthetic_smpc_underline.docx", fh, _DOCX_MIME)},
                                 data={"tenant_id": "plain-tenant"})
        self.assertEqual(r.status_code, 200, r.text[:400])
        self.body = r.json()

    def test_shape_and_no_u_element(self):
        self.assertEqual(set(self.body.keys()), _BASELINE_FIELDS)
        for field in ("original_xml", "xml", "bundle_xml"):
            self.assertNotRegex(self.body[field], r"<u\b", f"{field} carries a <u> element")
            self.assertIn('text-decoration: underline', self.body[field])

    def test_validator_reports_no_u_or_txt1_finding(self):
        msgs = " | ".join(str(i.get("message", "")) for i in self.body["issues"])
        self.assertNotIn("Invalid element name in the XHTML ('u')", msgs)
        self.assertNotIn("txt-1", msgs)


if __name__ == "__main__":
    unittest.main()
