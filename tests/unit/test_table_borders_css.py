"""
Unit tests for P0-8a — table / cell borders come from `static/epi-standard.css`,
not from inline attributes in the XHTML, when `inline_table_borders=False`.

Written BEFORE the implementation (CLAUDE.md §6 Step 4).

Run:
    python3 -m unittest tests.unit.test_table_borders_css -v
"""
from __future__ import annotations

import inspect
import os
import re
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import fhir_mapper as mapper  # noqa: E402

TABLE_HTML = "<p>Dose table</p><table><tr><th>Dose</th><td>50 mg</td></tr></table>"


def _doc(text=TABLE_HTML):
    return {"filename": "t.docx", "type": "SmPC",
            "sections": [{"section_id": "4.2", "title": "4.2 Posology and method of administration", "text": text}]}


def _section_div(comp) -> str:
    import json
    return json.loads(mapper.resource_to_json(comp))["section"][0]["section"][0]["text"]["div"]


class _Base(unittest.TestCase):
    def setUp(self):
        if "inline_table_borders" not in inspect.signature(mapper.create_doc_composition).parameters:
            self.fail("P0-8a not implemented: create_doc_composition lacks inline_table_borders= (FEATURE_SPEC §5 P0-8a)")


class MapperBorderTests(_Base):

    def test_flag_on_emits_bare_table_and_cells(self):
        comp = mapper.create_doc_composition(_doc(), "mp", "org", inline_table_borders=False)
        div = _section_div(comp)
        self.assertIn("<table>", div)
        self.assertNotRegex(div, r"<table[^>]*\b(border|style|width)=")
        self.assertNotRegex(div, r"<t[dh][^>]*\bstyle=")
        self.assertIn("<th>Dose</th>", div)
        self.assertIn("<td>50 mg</td>", div)

    def test_flag_off_is_todays_behaviour(self):
        comp_default = mapper.create_doc_composition(_doc(), "mp", "org")
        comp_explicit = mapper.create_doc_composition(_doc(), "mp", "org", inline_table_borders=True)
        for comp in (comp_default, comp_explicit):
            div = _section_div(comp)
            self.assertIn('border="1"', div)
            self.assertIn("border-collapse: collapse", div)
            self.assertIn("border: 1px solid black; padding: 4px;", div)

    def test_source_whitelisted_styles_survive_either_way(self):
        html = '<table><tr><td style="text-align: center">x</td></tr></table>'
        div = _section_div(mapper.create_doc_composition(_doc(html), "mp", "org", inline_table_borders=False))
        self.assertIn('<td style="text-align: center">', div)

    def test_generate_bundle_passes_the_flag_through(self):
        import json
        b = json.loads(mapper.resource_to_json(mapper.generate_bundle([_doc()], inline_table_borders=False)))
        comps = [e["resource"] for e in b["entry"] if e["resource"]["resourceType"] == "Composition"]
        self.assertEqual(len(comps), 1)
        div = comps[0]["section"][0]["section"][0]["text"]["div"]
        self.assertNotIn('border="1"', div)


class FixerBorderTests(unittest.TestCase):
    """Phase 1 AutoFixer must not re-inject the borders the mapper left out."""

    def setUp(self):
        try:
            import fhir_validator as fv
        except ImportError as exc:  # pragma: no cover
            self.skipTest(f"fhir_validator import failed in this environment: {exc}")
        self.fv = fv
        if "inline_table_borders" not in inspect.signature(fv.AutoFixer.__init__).parameters:
            self.fail("P0-8a not implemented: AutoFixer lacks inline_table_borders= (FEATURE_SPEC §5 P0-8a)")
        if "inline_table_borders" not in inspect.signature(fv.run_validation_pipeline).parameters:
            self.fail("P0-8a not implemented: run_validation_pipeline lacks inline_table_borders=")

    XML = ('<Composition xmlns="http://hl7.org/fhir"><section><text><div xmlns="http://www.w3.org/1999/xhtml">'
           '<table cellspacing="0"><tr><td>x</td></tr></table></div></text></section></Composition>')

    def _issue(self, msg):
        return self.fv.ValidationIssue(severity="error", message=msg, location="div", line=1)

    def test_flag_on_skips_injection_but_still_strips_rejected_attrs(self):
        fixer = self.fv.AutoFixer(inline_table_borders=False)
        out, fixes = fixer._fix_table_borders(self.XML, [self._issue("The attribute cellspacing is not allowed")])
        self.assertNotIn("cellspacing", out)
        self.assertNotIn('border="1"', out)
        self.assertNotIn("style=", out)
        self.assertFalse(any(f.rule == "UI_FORMAT_TABLE_BORDERS" for f in fixes))

    def test_flag_on_strip_is_audited_through_fix(self):
        fixer = self.fv.AutoFixer(inline_table_borders=False)
        out, actions = fixer.fix(self.XML, [self._issue("The attribute cellspacing is not allowed")])
        self.assertNotIn("cellspacing", out)
        self.assertTrue(any(a.rule == "XHTML_TABLE_ATTRS_STRIPPED" for a in actions),
                        "a changed XML must leave a fix_log row (ALCOA+ Accurate)")
        again, actions2 = fixer.fix(out, [self._issue("The attribute cellspacing is not allowed")])
        self.assertEqual(again, out)
        self.assertFalse(any(a.rule == "XHTML_TABLE_ATTRS_STRIPPED" for a in actions2), "idempotent: no second row")

    def test_flag_off_injects_as_today(self):
        fixer = self.fv.AutoFixer()
        out, fixes = fixer._fix_table_borders(self.XML, [])
        self.assertIn('border="1"', out)
        self.assertTrue(any(f.rule == "UI_FORMAT_TABLE_BORDERS" for f in fixes))

    def test_idempotent_both_ways(self):
        for flag in (True, False):
            fixer = self.fv.AutoFixer(inline_table_borders=flag)
            once, _ = fixer._fix_table_borders(self.XML, [])
            twice, _ = fixer._fix_table_borders(once, [])
            self.assertEqual(once, twice, f"inline_table_borders={flag}")


class StylesheetTests(unittest.TestCase):

    def test_css_owns_the_borders(self):
        css = open(os.path.join(_REPO_ROOT, "static", "epi-standard.css"), encoding="utf-8").read()
        table_rule = re.search(r"\.epi-narrative table\s*\{([^}]*)\}", css)
        cell_rule = re.search(r"\.epi-narrative th,\s*\.epi-narrative td\s*\{([^}]*)\}", css)
        self.assertIsNotNone(table_rule); self.assertIsNotNone(cell_rule)
        self.assertIn("border-collapse: collapse", table_rule.group(1))
        self.assertRegex(table_rule.group(1), r"border:\s*1px solid")
        self.assertRegex(cell_rule.group(1), r"border:\s*1px solid")


if __name__ == "__main__":
    unittest.main()
