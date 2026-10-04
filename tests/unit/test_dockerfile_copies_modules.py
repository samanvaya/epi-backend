"""
Guard: every first-party module the service imports must be COPY'd into the
Docker image. The Dockerfile copies files explicitly; a module added to the
repo but not to the Dockerfile boots fine locally and crashes in production
with ModuleNotFoundError (this happened on 2026-10-04 with feature_flags.py —
deploy dep-db1bsitg1s2s739fk740 rolled back).

Run:
    python3 -m unittest tests.unit.test_dockerfile_copies_modules -v
"""
from __future__ import annotations

import ast
import os
import re
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_ENTRY = "main.py"


def _first_party_imports(start: str) -> set:
    """Transitive closure of top-level repo modules imported from `start`."""
    seen, todo = set(), [start]
    while todo:
        name = todo.pop()
        path = os.path.join(_REPO_ROOT, name)
        if not os.path.exists(path):
            continue
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                mods = [node.module]
            for m in mods:
                top = m.split(".")[0]
                candidate = f"{top}.py"
                if os.path.exists(os.path.join(_REPO_ROOT, candidate)) and candidate not in seen:
                    seen.add(candidate)
                    todo.append(candidate)
    return seen


class DockerfileCopiesModulesTests(unittest.TestCase):

    def test_every_imported_module_is_copied(self):
        dockerfile = open(os.path.join(_REPO_ROOT, "Dockerfile"), encoding="utf-8").read()
        copied = set(re.findall(r"^\s*COPY\s+(\S+\.py)\s+\.", dockerfile, re.MULTILINE))
        needed = _first_party_imports(_ENTRY) | {_ENTRY}
        missing = sorted(needed - copied)
        self.assertEqual(missing, [], f"modules imported by {_ENTRY} but not COPY'd in Dockerfile: {missing}")


if __name__ == "__main__":
    unittest.main()
