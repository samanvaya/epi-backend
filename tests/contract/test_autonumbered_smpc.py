"""
Contract test for P0-3a over the public HTTP surface.

An SmPC whose QRD numbers exist only as Word automatic numbering must pass the
P0-2 structural gate and produce the same section structure as its
typed-number twin. Before P0-3a this fixture returned
`422 … Detected 1 SmPC section anchor(s); need at least 2`.

Refs: FEATURE_SPEC.md §5 P0-3a, P0-2; CLAUDE.md §7.4 (error-path tests), §5.8.

Run:
    python3 -m unittest tests.contract.test_autonumbered_smpc -v
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_FIXTURES = os.path.join(_REPO_ROOT, "tests", "fixtures")
_AUTONUM = os.path.join(_FIXTURES, "synthetic_smpc_autonum.docx")
_TYPED = os.path.join(_FIXTURES, "synthetic_smpc.docx")
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

_BASELINE_FIELDS = frozenset({
    "status", "error_count", "warning_count", "info_count", "summary", "iterations",
    "original_xml", "xml", "issues", "fix_log", "validation_log_json",
    "validation_report_md", "fidelity_score", "fidelity_status", "diff_html",
    "bundle_json", "bundle_xml", "source_text", "doc_type", "sections_count", "css_href",
})


class AutoNumberedSmpcTests(unittest.TestCase):

    def setUp(self):
        for p in (_AUTONUM, _TYPED):
            if not os.path.exists(p):
                self.skipTest(f"fixture missing: {p}")
        from fastapi.testclient import TestClient
        import main as main_module
        self.client = TestClient(main_module.app)

    def _post(self, path: str):
        with open(path, "rb") as fh:
            return self.client.post(
                "/api/process_stateless",
                files={"file": (os.path.basename(path), fh, _DOCX_MIME)},
                data={"tenant_id": "plain-tenant"},
            )

    def test_auto_numbered_smpc_passes_the_structural_gate(self):
        r = self._post(_AUTONUM)
        self.assertEqual(r.status_code, 200, r.text[:400])
        body = r.json()
        self.assertEqual(set(body.keys()), _BASELINE_FIELDS)
        self.assertEqual(body["doc_type"], "SmPC")

    def test_same_sections_as_typed_number_twin(self):
        auto, typed = self._post(_AUTONUM).json(), self._post(_TYPED).json()
        self.assertEqual(auto["sections_count"], typed["sections_count"])
        # Section headings in the narrative are identical (numbers now visible).
        for heading in ("4.1 Therapeutic indications", "4.8 Undesirable effects", "6.1 List of excipients"):
            self.assertIn(heading, auto["xml"])
        if auto["fidelity_status"] == "available" and typed["fidelity_status"] == "available":
            # The body list adds a few words; otherwise the two must score alike (CLAUDE.md §5.8).
            self.assertAlmostEqual(auto["fidelity_score"], typed["fidelity_score"], delta=1.0)

    def test_body_list_survives_as_a_list(self):
        body = self._post(_AUTONUM).json()
        self.assertIn("<li>Take one tablet", body["xml"].replace("\n", ""))
        self.assertNotIn("1. Take one tablet", body["source_text"])


if __name__ == "__main__":
    unittest.main()
