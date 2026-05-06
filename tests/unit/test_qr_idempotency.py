"""
Unit tests for the publication idempotency contract (P1-PUB-3) and the
deterministic QR generator (P1-PUB-1 / P1-PUB-3).

These tests must pass before the publish path can be defended to a QA Lead.

Refs: FEATURE_SPEC.md §5 P1-PUB-1, P1-PUB-3; CLAUDE.md §5.5 (idempotency mandatory).

Run:
    python3 -m unittest tests.unit.test_qr_idempotency -v
"""
from __future__ import annotations

import hashlib
import os
import sys
import unittest

# Make repo modules importable when running tests from the repo root.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


class QRGeneratorDeterminismTests(unittest.TestCase):
    """qr_generator.svg_for_url must be byte-deterministic for the same URL."""

    def test_same_url_yields_same_svg_bytes(self):
        from qr_generator import svg_for_url

        url = "https://epi.antigravity.eu/r/00000000-0000-5000-8000-000000000001"
        a = svg_for_url(url)
        b = svg_for_url(url)
        self.assertIsInstance(a, bytes)
        self.assertEqual(a, b, "svg_for_url must be deterministic for the same URL")

    def test_different_urls_yield_different_svg_bytes(self):
        from qr_generator import svg_for_url

        a = svg_for_url("https://epi.antigravity.eu/r/aaaaaaaa-aaaa-5aaa-8aaa-aaaaaaaaaaaa")
        b = svg_for_url("https://epi.antigravity.eu/r/bbbbbbbb-bbbb-5bbb-8bbb-bbbbbbbbbbbb")
        self.assertNotEqual(a, b)

    def test_svg_starts_with_svg_tag(self):
        from qr_generator import svg_for_url

        out = svg_for_url("https://example.com/r/123")
        self.assertTrue(
            out.lstrip().startswith(b"<?xml") or out.lstrip().startswith(b"<svg"),
            "svg_for_url should produce SVG bytes",
        )


class PublicationIdDerivationTests(unittest.TestCase):
    """derive_publication_id must be deterministic across (tenant_id, bundle_sha256)."""

    def test_same_tenant_same_hash_yields_same_id(self):
        from publication_service import derive_publication_id

        sha = hashlib.sha256(b"some-bundle-bytes").hexdigest()
        a = derive_publication_id("tenant-acme", sha)
        b = derive_publication_id("tenant-acme", sha)
        self.assertEqual(a, b)

    def test_different_tenants_yield_different_ids(self):
        from publication_service import derive_publication_id

        sha = hashlib.sha256(b"some-bundle-bytes").hexdigest()
        a = derive_publication_id("tenant-acme", sha)
        b = derive_publication_id("tenant-beta", sha)
        self.assertNotEqual(a, b)

    def test_different_hashes_yield_different_ids(self):
        from publication_service import derive_publication_id

        a = derive_publication_id(
            "tenant-acme", hashlib.sha256(b"bundle-one").hexdigest()
        )
        b = derive_publication_id(
            "tenant-acme", hashlib.sha256(b"bundle-two").hexdigest()
        )
        self.assertNotEqual(a, b)

    def test_id_is_uuid_v5_string(self):
        import re

        from publication_service import derive_publication_id

        out = derive_publication_id(
            "tenant-acme", hashlib.sha256(b"x").hexdigest()
        )
        # UUID v5 string format: 8-4-4-4-12, version digit '5' in third group, variant in fourth
        self.assertRegex(
            out,
            r"^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        )


class PublishBundleIdempotencyTests(unittest.TestCase):
    """publish_bundle must be idempotent (CLAUDE.md §5.5)."""

    def setUp(self):
        # Use a temp DB for each test so state does not leak between tests.
        import tempfile

        self._tmpdir = tempfile.mkdtemp(prefix="pub-itest-")
        os.environ["PUBLICATION_DB_PATH"] = os.path.join(self._tmpdir, "publications.db")
        os.environ["PUBLICATION_PUBLIC_BASE_URL"] = "https://test.example.com"

    def tearDown(self):
        import shutil

        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_publish_same_bundle_twice_returns_same_record(self):
        from publication_service import publish_bundle

        xhtml = "<div xmlns='http://www.w3.org/1999/xhtml'>Hello world</div>"
        bundle_sha = hashlib.sha256(xhtml.encode("utf-8")).hexdigest()

        first = publish_bundle(
            tenant_id="tenant-acme",
            bundle_sha256=bundle_sha,
            xhtml=xhtml,
            language="en",
            validator_outcome="validated",
            fidelity_score=99.5,
            correlation_id="corr-001",
            actor_id="user-001",
        )
        second = publish_bundle(
            tenant_id="tenant-acme",
            bundle_sha256=bundle_sha,
            xhtml=xhtml,
            language="en",
            validator_outcome="validated",
            fidelity_score=99.5,
            correlation_id="corr-002",  # different correlation, same content
            actor_id="user-001",
        )

        self.assertEqual(first.publication_id, second.publication_id)
        self.assertEqual(first.qr_svg, second.qr_svg)
        self.assertEqual(first.xhtml, second.xhtml)

    def test_republish_emits_audit_event(self):
        from publication_service import publish_bundle, list_audit_events

        xhtml = "<div xmlns='http://www.w3.org/1999/xhtml'>Hello world</div>"
        bundle_sha = hashlib.sha256(xhtml.encode("utf-8")).hexdigest()

        publish_bundle(
            tenant_id="tenant-acme",
            bundle_sha256=bundle_sha,
            xhtml=xhtml,
            language="en",
            validator_outcome="validated",
            fidelity_score=99.5,
            correlation_id="corr-A",
            actor_id="user-001",
        )
        publish_bundle(
            tenant_id="tenant-acme",
            bundle_sha256=bundle_sha,
            xhtml=xhtml,
            language="en",
            validator_outcome="validated",
            fidelity_score=99.5,
            correlation_id="corr-B",
            actor_id="user-001",
        )

        events = list_audit_events()
        kinds = [e["event"] for e in events]
        self.assertIn("publication.created", kinds)
        self.assertIn("publication.republished", kinds)


if __name__ == "__main__":
    unittest.main(verbosity=2)
