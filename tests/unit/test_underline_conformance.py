"""
Unit tests for P0-3b — underline is emitted as
`<span style="text-decoration: underline">`, never `<u>` (FHIR `txt-1`;
EMA samples EPI-25-100 / EPI-23-1022).

Written BEFORE the implementation (CLAUDE.md §6 Step 4).

Run:
    python3 -m unittest tests.unit.test_underline_conformance -v
"""
from __future__ import annotations

import os
import re
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import doc_parser  # noqa: E402

_FIXTURE = os.path.join(_REPO_ROOT, "tests", "fixtures", "synthetic_smpc_underline.docx")
UNDERLINE_SPAN = '<span style="text-decoration: underline">'

try:
    import mammoth  # noqa: F401
    _HAVE_MAMMOTH = True
except ImportError:  # pragma: no cover
    _HAVE_MAMMOTH = False


class SanitiserUnderlineTests(unittest.TestCase):

    def test_u_element_is_rewritten_to_styled_span(self):
        out = doc_parser._sanitize_html_styles("<p>Read <u>this</u> first.</p>")
        self.assertEqual(out, f"<p>Read {UNDERLINE_SPAN}this</span> first.</p>")

    def test_marker_class_is_rewritten_to_styled_span(self):
        out = doc_parser._sanitize_html_styles('<p><span class="epi-underline">x</span></p>')
        self.assertEqual(out, f"<p>{UNDERLINE_SPAN}x</span></p>")

    def test_u_with_attributes_and_mixed_case(self):
        out = doc_parser._sanitize_html_styles('<p><U class="a" style="color:red">x</U></p>')
        self.assertEqual(out, f"<p>{UNDERLINE_SPAN}x</span></p>")

    def test_only_underline_value_survives_whitelist(self):
        cases = {
            'style="text-decoration: underline"': UNDERLINE_SPAN,
            'style="text-decoration: underline;"': UNDERLINE_SPAN,
            'style="TEXT-DECORATION: Underline"': UNDERLINE_SPAN,
            'style="text-decoration: line-through"': "<span>",
            'style="text-decoration: none"': "<span>",
            'style="text-decoration: underline; color: red; font-size: 9pt"': UNDERLINE_SPAN,
            'style="text-decoration: underline red wavy"': "<span>",
        }
        for attr, expected_open in cases.items():
            out = doc_parser._sanitize_html_styles(f"<p><span {attr}>x</span></p>")
            self.assertEqual(out, f"<p>{expected_open}x</span></p>", attr)

    def test_idempotent(self):
        html = "<p>a <u>b</u> c <span class=\"epi-underline\">d</span></p>"
        once = doc_parser._sanitize_html_styles(html)
        self.assertEqual(doc_parser._sanitize_html_styles(once), once)

    def test_no_u_in_output_ever(self):
        html = "<p><u><b>bold under</b></u><u></u><u>x<i>y</i></u></p>"
        out = doc_parser._sanitize_html_styles(html)
        self.assertNotRegex(out, r"</?u\b", out)

    def test_existing_whitelist_behaviour_unchanged(self):
        # text-align / borders still pass; fonts / colours still stripped.
        html = '<p style="text-align: center; font-family: Arial; color: red">x</p>'
        self.assertEqual(doc_parser._sanitize_html_styles(html), '<p style="text-align: center">x</p>')


class ReadDocxUnderlineTests(unittest.TestCase):

    def setUp(self):
        if not os.path.exists(_FIXTURE):
            self.skipTest("fixture missing (run tests/fixtures/gen_synthetic_smpc_underline.py)")
        if not _HAVE_MAMMOTH:
            self.skipTest("mammoth not installed in this environment")

    def test_underlined_run_becomes_styled_span(self):
        html = doc_parser.read_docx(_FIXTURE)
        self.assertNotRegex(html, r"<u\b", "no <u> element may reach the narrative")
        self.assertIn(UNDERLINE_SPAN + "must be read before use (fictional underlined warning)</span>", html)

    def test_sections_identical_to_plain_fixture(self):
        plain = os.path.join(_REPO_ROOT, "tests", "fixtures", "synthetic_smpc.docx")
        if not os.path.exists(plain):
            self.skipTest("plain fixture missing")
        a = [s["section_id"] for s in doc_parser.parse_document(_FIXTURE)]
        b = [s["section_id"] for s in doc_parser.parse_document(plain)]
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
