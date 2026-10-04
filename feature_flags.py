"""Per-tenant feature flags (CLAUDE.md §5.7).

New behaviour that changes a regulated output ships default-off behind a
comma-separated tenant allowlist read from the environment. `tenant_enabled`
is the single reader for the flags introduced from 2026-10-04 on:

    NESTED_DOCUMENT_BUNDLE_TENANTS_ALLOWLIST   P0-4a  one `document` Bundle per Composition
    CSS_TABLE_BORDERS_TENANTS_ALLOWLIST        P0-8a  table borders from the stylesheet only

The earlier `PUBLICATION_TENANTS_ALLOWLIST` (`publication_service`) and
`IMAGE_BINARIES_TENANTS_ALLOWLIST` (`image_embedder`) keep their own readers
— identical semantics, left untouched for byte-identity of those paths.

Flags are read at call time, not import time, so tests and ops can change
them without a restart of the module graph. `tenant_id` is a client-asserted
form field today; binding it to an authenticated identity is Sprint-1 SSO work.
"""
from __future__ import annotations

import os

NESTED_DOCUMENT_BUNDLE = "NESTED_DOCUMENT_BUNDLE_TENANTS_ALLOWLIST"
CSS_TABLE_BORDERS = "CSS_TABLE_BORDERS_TENANTS_ALLOWLIST"


def tenant_enabled(env_var: str, tenant_id: str) -> bool:
    """True when `tenant_id` is non-empty and listed in the env var (comma-separated)."""
    raw = os.environ.get(env_var, "")
    allowed = {t.strip() for t in raw.split(",") if t.strip()}
    return bool(tenant_id) and tenant_id in allowed
