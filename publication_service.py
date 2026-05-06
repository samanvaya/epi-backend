"""
Publication service for the v1 demo QR / render path.

Responsibilities:

1. **Derive a deterministic publication_id** from `(tenant_id, bundle_sha256)`
   using UUID v5 — so re-publishing the same bundle for the same tenant
   yields the same id, the same render URL, and the same QR code (P1-PUB-3
   idempotency).

2. **Persist the rendered XHTML** for a publication, write-once, in a small
   SQLite database. The store is forward-compatible with the Sprint 2
   Postgres + content-addressed object-storage migration.

3. **Render the XHTML page** that the QR resolves to: the stored bundle's
   narrative wrapped in a page chrome that links the canonical
   `epi-standard.css`, declares `<meta name="publication-stability"
   content="preview">` (P1-PUB-2 watermark requirement), and embeds a footer
   disclosing truncated `bundle_sha256`, validator outcome, `published_at`
   (ISO-8601 UTC), and `correlation_id`.

4. **Emit append-only audit rows** for every lifecycle event:
   `publication.created`, `publication.served`, `publication.republished`,
   `publication.revoked`. No scanner PII (IP, user-agent) is logged
   (CLAUDE.md §4.5; FEATURE_SPEC §8 Q12).

What this module deliberately does NOT do (v1 demo scope):

- No multi-language negotiation. The render is single-language — the
  language of the originally-uploaded SmPC. Multi-language is P2-PUB-LANG.
- No CDN, no rate limiting, no DDoS posture. Public exposure is gated on
  the `PUBLICATION_TENANTS_ALLOWLIST` env var (i.e. design partners only)
  until P2-PUB-PROD ships.
- No transforms at scan time. The XHTML stored at `publish_bundle` time is
  served byte-for-byte. We never re-derive from the source DOCX. CLAUDE.md
  §10 #9 (never auto-rewrite labelling content).
- No e-signatures on publish. Sprint 3 Part-11 work covers that.

Refs:
- FEATURE_SPEC.md §5 P1-PUB-1..4; §5 P2-PUB-LANG, P2-PUB-PROD; §7 traceability
- CLAUDE.md §4.1 (ALCOA+ on regulated records), §5 (no-regression contract),
  §5.5 (idempotency), §10 (#1, #2, #9, #12 bright lines)
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator, List, Optional

import qr_generator


logger = logging.getLogger(__name__)

# Stable UUID v5 namespace for derive_publication_id. Generated once, then
# frozen — changing this value is a public-contract break (existing QRs would
# stop matching their stored publications). Treat as a constant of the API.
_NAMESPACE_PUBLICATION = uuid.UUID("a8f5f167-8c7e-5d3b-9b1a-2c4e6f8a0b1c")


# ----- env-driven configuration ------------------------------------------------


def _db_path() -> str:
    """Resolve the SQLite database path. Default: `<repo>/data/publications.db`."""
    explicit = os.environ.get("PUBLICATION_DB_PATH")
    if explicit:
        os.makedirs(os.path.dirname(explicit) or ".", exist_ok=True)
        return explicit
    repo = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(repo, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "publications.db")


def _public_base_url() -> str:
    """Base URL used to build the QR's render URL. Override in prod."""
    return os.environ.get(
        "PUBLICATION_PUBLIC_BASE_URL", "http://localhost:8000"
    ).rstrip("/")


def tenant_is_allowlisted(tenant_id: str) -> bool:
    """Per-tenant feature flag check (CLAUDE.md §5.7).

    For v1 demo, the flag is read from the `PUBLICATION_TENANTS_ALLOWLIST`
    environment variable (comma-separated tenant slugs). The Postgres-backed
    tenant config table replaces this in Sprint 1.
    """
    raw = os.environ.get("PUBLICATION_TENANTS_ALLOWLIST", "")
    allowed = {t.strip() for t in raw.split(",") if t.strip()}
    return bool(tenant_id) and tenant_id in allowed


# ----- DB schema --------------------------------------------------------------


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS publications (
    publication_id    TEXT PRIMARY KEY,
    tenant_id         TEXT NOT NULL,
    bundle_sha256     TEXT NOT NULL,
    xhtml             TEXT NOT NULL,
    qr_svg_b64        TEXT NOT NULL,
    language          TEXT NOT NULL,
    validator_outcome TEXT NOT NULL,
    fidelity_score    REAL,
    created_at        TEXT NOT NULL,
    revoked_at        TEXT,
    revocation_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_publications_tenant_hash
    ON publications(tenant_id, bundle_sha256);

CREATE TABLE IF NOT EXISTS publication_audit (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    publication_id TEXT NOT NULL,
    event          TEXT NOT NULL,
    actor_id       TEXT,
    tenant_id      TEXT,
    correlation_id TEXT,
    occurred_at    TEXT NOT NULL,
    payload_json   TEXT
);

CREATE INDEX IF NOT EXISTS idx_publication_audit_pub
    ON publication_audit(publication_id, occurred_at);
"""


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    try:
        # Apply schema on every open — cheap, idempotent, keeps the v1 demo
        # tolerant of fresh checkouts and per-test temp DBs.
        conn.executescript(_SCHEMA_SQL)
        yield conn
        conn.commit()
    finally:
        conn.close()


# ----- public dataclasses -----------------------------------------------------


@dataclass(frozen=True)
class PublicationRecord:
    publication_id: str
    tenant_id: str
    bundle_sha256: str
    xhtml: str
    qr_svg: str               # base64-encoded SVG bytes
    render_url: str
    language: str
    validator_outcome: str
    fidelity_score: Optional[float]
    created_at: str           # ISO-8601 UTC
    revoked_at: Optional[str] = None
    revocation_reason: Optional[str] = None


# ----- core API ---------------------------------------------------------------


def derive_publication_id(tenant_id: str, bundle_sha256: str) -> str:
    """Deterministic UUID v5 from `(tenant_id, bundle_sha256)`.

    Re-publishing the same bundle for the same tenant returns the same id —
    the cornerstone of P1-PUB-3 idempotency.
    """
    if not tenant_id:
        raise ValueError("derive_publication_id: tenant_id required")
    if not bundle_sha256:
        raise ValueError("derive_publication_id: bundle_sha256 required")
    return str(uuid.uuid5(_NAMESPACE_PUBLICATION, f"{tenant_id}:{bundle_sha256}"))


def render_url_for(publication_id: str) -> str:
    return f"{_public_base_url()}/api/v1/render/{publication_id}"


def publish_bundle(
    *,
    tenant_id: str,
    bundle_sha256: str,
    xhtml: str,
    language: str,
    validator_outcome: str,
    fidelity_score: Optional[float],
    correlation_id: str,
    actor_id: str,
) -> PublicationRecord:
    """Idempotently publish a bundle.

    Parameters carry semantic constraints:
    - `validator_outcome` must be one of `"validated"` or `"partially_fixed"`.
      Caller (main.process_stateless) gates the publish flag on
      `status ∈ {"validated", "partially_fixed"}` and returns 409 otherwise
      (CLAUDE.md §10 #12: never publish a non-conforming bundle).
    - `xhtml` is the rendered narrative as it will be served on scan. Stored
      byte-for-byte; never re-derived.
    """
    if validator_outcome not in {"validated", "partially_fixed"}:
        raise ValueError(
            f"publish_bundle: validator_outcome must be 'validated' or "
            f"'partially_fixed' (got {validator_outcome!r})"
        )

    pub_id = derive_publication_id(tenant_id, bundle_sha256)
    render_url = render_url_for(pub_id)
    qr_svg_b64 = qr_generator.svg_for_url_b64(render_url)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with _connect() as conn:
        existing = conn.execute(
            "SELECT * FROM publications WHERE publication_id = ?", (pub_id,)
        ).fetchone()

        if existing is not None:
            # Idempotent path — emit republished audit event, return the existing record.
            _emit_audit(
                conn,
                publication_id=pub_id,
                event="publication.republished",
                actor_id=actor_id,
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                payload={"bundle_sha256": bundle_sha256},
            )
            return _row_to_record(existing, render_url=render_url)

        conn.execute(
            """
            INSERT INTO publications (
                publication_id, tenant_id, bundle_sha256, xhtml, qr_svg_b64,
                language, validator_outcome, fidelity_score, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pub_id,
                tenant_id,
                bundle_sha256,
                xhtml,
                qr_svg_b64,
                language,
                validator_outcome,
                fidelity_score,
                now,
            ),
        )
        _emit_audit(
            conn,
            publication_id=pub_id,
            event="publication.created",
            actor_id=actor_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            payload={
                "bundle_sha256": bundle_sha256,
                "language": language,
                "validator_outcome": validator_outcome,
                "fidelity_score": fidelity_score,
            },
        )

    return PublicationRecord(
        publication_id=pub_id,
        tenant_id=tenant_id,
        bundle_sha256=bundle_sha256,
        xhtml=xhtml,
        qr_svg=qr_svg_b64,
        render_url=render_url,
        language=language,
        validator_outcome=validator_outcome,
        fidelity_score=fidelity_score,
        created_at=now,
    )


def lookup(publication_id: str) -> Optional[PublicationRecord]:
    """Read-only lookup by id. Returns None if no row exists."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM publications WHERE publication_id = ?", (publication_id,)
        ).fetchone()
    if row is None:
        return None
    return _row_to_record(row, render_url=render_url_for(publication_id))


def revoke_publication(
    *,
    publication_id: str,
    actor_id: str,
    tenant_id: str,
    correlation_id: str,
    reason: str,
) -> None:
    """Mark a publication as revoked (soft-delete).

    The row is NOT physically deleted (CLAUDE.md §10 #2: never delete a
    regulated record). Subsequent `GET /api/v1/render/{id}` returns 410 Gone.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with _connect() as conn:
        conn.execute(
            """
            UPDATE publications
               SET revoked_at = ?, revocation_reason = ?
             WHERE publication_id = ?
            """,
            (now, reason, publication_id),
        )
        _emit_audit(
            conn,
            publication_id=publication_id,
            event="publication.revoked",
            actor_id=actor_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            payload={"reason": reason},
        )


def record_served(
    *,
    publication_id: str,
    correlation_id: str,
) -> None:
    """Record a successful render. NO scanner PII (IP, UA) — by design.

    Aggregate scan_count is computed by counting rows; per-scan analytics with
    PII is out of scope for v1 (FEATURE_SPEC §8 Q12).
    """
    with _connect() as conn:
        _emit_audit(
            conn,
            publication_id=publication_id,
            event="publication.served",
            actor_id=None,        # anonymous render
            tenant_id=None,       # not bound to a tenant session
            correlation_id=correlation_id,
            payload=None,
        )


def list_audit_events(publication_id: Optional[str] = None) -> List[dict]:
    """Read-only audit dump. Used by tests and by the inspector view."""
    with _connect() as conn:
        if publication_id is None:
            rows = conn.execute(
                "SELECT * FROM publication_audit ORDER BY id ASC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM publication_audit WHERE publication_id = ? ORDER BY id ASC",
                (publication_id,),
            ).fetchall()
    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "publication_id": r["publication_id"],
            "event": r["event"],
            "actor_id": r["actor_id"],
            "tenant_id": r["tenant_id"],
            "correlation_id": r["correlation_id"],
            "occurred_at": r["occurred_at"],
            "payload": json.loads(r["payload_json"]) if r["payload_json"] else None,
        })
    return out


# ----- rendering --------------------------------------------------------------


# Single-source-of-truth wording for the preview watermark / banner.
# Changing this requires an explicit FEATURE_SPEC amendment (P1-PUB-2).
_PREVIEW_BANNER = (
    "Preview — not packaging-grade. This rendered ePI is from a v1 demo "
    "publication. Multi-language negotiation and production-grade resolver "
    "SLA are pending (P2-PUB-LANG, P2-PUB-PROD)."
)


def render_xhtml(record: PublicationRecord, css_href: str = "/static/epi-standard.css") -> str:
    """Wrap the stored bundle XHTML in a public-render page chrome.

    The chrome contributes:
    - `<!DOCTYPE html>` + `<html xmlns="http://www.w3.org/1999/xhtml">`.
    - `<link rel="stylesheet" href="{css_href}">` — the canonical stylesheet.
    - `<meta name="publication-stability" content="preview">` — required until
      P2-PUB-LANG and P2-PUB-PROD ship.
    - A "preview" banner above the narrative.
    - A footer disclosure block: truncated `bundle_sha256`, validator outcome,
      `published_at`, `correlation_id` (placeholder; the route layer fills the
      live correlation id on each render).
    - The stored narrative XHTML, served verbatim — no transforms.
    """
    short_sha = record.bundle_sha256[:12]
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" lang="' + record.language + '">\n'
        '<head>\n'
        '  <meta charset="UTF-8"/>\n'
        '  <meta name="publication-stability" content="preview"/>\n'
        '  <meta name="publication-id" content="' + record.publication_id + '"/>\n'
        '  <meta name="bundle-sha256" content="' + record.bundle_sha256 + '"/>\n'
        '  <title>ePI — preview render — ' + record.publication_id + '</title>\n'
        '  <link rel="stylesheet" href="' + css_href + '"/>\n'
        '  <style>\n'
        '    .epi-preview-banner { background: #fff3cd; border: 1px solid #ffeeba;\n'
        '      padding: 8px 12px; margin: 0 0 16px 0; font-size: 90%;\n'
        '      font-family: Times New Roman, serif; }\n'
        '    .epi-render-footer { margin-top: 32px; padding-top: 12px;\n'
        '      border-top: 1px solid #ccc; font-size: 80%; color: #555;\n'
        '      font-family: Times New Roman, serif; }\n'
        '    .epi-render-footer dt { font-weight: bold; float: left;\n'
        '      width: 12em; clear: left; }\n'
        '  </style>\n'
        '</head>\n'
        '<body>\n'
        '  <div class="epi-preview-banner">' + _PREVIEW_BANNER + '</div>\n'
        '  ' + record.xhtml + '\n'
        '  <footer class="epi-render-footer">\n'
        '    <dl>\n'
        '      <dt>publication_id</dt><dd>' + record.publication_id + '</dd>\n'
        '      <dt>bundle_sha256</dt><dd>' + short_sha + '…</dd>\n'
        '      <dt>validator_outcome</dt><dd>' + record.validator_outcome + '</dd>\n'
        '      <dt>published_at</dt><dd>' + record.created_at + '</dd>\n'
        '      <dt>language</dt><dd>' + record.language + '</dd>\n'
        '    </dl>\n'
        '  </footer>\n'
        '</body>\n'
        '</html>\n'
    )


# ----- internals --------------------------------------------------------------


def _emit_audit(
    conn: sqlite3.Connection,
    *,
    publication_id: str,
    event: str,
    actor_id: Optional[str],
    tenant_id: Optional[str],
    correlation_id: Optional[str],
    payload: Optional[dict],
) -> None:
    """Append-only audit row (CLAUDE.md §4.1 ALCOA+: Attributable, Legible,
    Contemporaneous, Original, Accurate)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute(
        """
        INSERT INTO publication_audit (
            publication_id, event, actor_id, tenant_id,
            correlation_id, occurred_at, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            publication_id,
            event,
            actor_id,
            tenant_id,
            correlation_id,
            now,
            json.dumps(payload, sort_keys=True) if payload is not None else None,
        ),
    )
    logger.info(
        "publication_audit %s pub=%s actor=%s tenant=%s corr=%s",
        event, publication_id, actor_id, tenant_id, correlation_id,
    )


def _row_to_record(row: sqlite3.Row, *, render_url: str) -> PublicationRecord:
    return PublicationRecord(
        publication_id=row["publication_id"],
        tenant_id=row["tenant_id"],
        bundle_sha256=row["bundle_sha256"],
        xhtml=row["xhtml"],
        qr_svg=row["qr_svg_b64"],
        render_url=render_url,
        language=row["language"],
        validator_outcome=row["validator_outcome"],
        fidelity_score=row["fidelity_score"],
        created_at=row["created_at"],
        revoked_at=row["revoked_at"],
        revocation_reason=row["revocation_reason"],
    )
