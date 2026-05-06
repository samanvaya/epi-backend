"""
Deterministic QR code generation for the publication path.

`svg_for_url(url)` returns bytes that encode a scannable QR pointing at the URL.
Same URL in → same bytes out, every time. This is the property that makes the
publication idempotency contract (P1-PUB-3) defensible end-to-end:

    publication_id = uuid5(NAMESPACE, f"{tenant_id}:{bundle_sha256}")
    render_url     = f"{PUBLIC_BASE}/r/{publication_id}"
    qr_svg         = svg_for_url(render_url)

Same bundle for the same tenant ⇒ same publication_id ⇒ same render_url ⇒
same SVG bytes ⇒ same printable artefact.

Refs:
- FEATURE_SPEC.md §5 P1-PUB-1, P1-PUB-3
- CLAUDE.md §5.5 (idempotency mandatory for any new fixer / generator)
- HL7 ePI / EMA Common Standard reference (the eventual packaging-grade
  resolver target). Until P2-PUB-LANG and P2-PUB-PROD ship, the rendered
  page carries a "preview" watermark — see publication_service.render_xhtml.
"""
from __future__ import annotations

import base64
from io import BytesIO

import qrcode
from qrcode.image.svg import SvgPathImage


# Error correction level. Tuned for "scannable from a phone at carton
# distance" while keeping the printed artefact compact. M = ~15% recovery.
# Do NOT change this without an explicit P1-PUB amendment + spec note +
# regenerated golden corpus baselines.
_ERROR_CORRECTION = qrcode.constants.ERROR_CORRECT_M

# Box-size = pixels per module in the SVG path output. 10 is a balance between
# legibility on phone screens and total SVG byte size for embedding in JSON.
_BOX_SIZE = 10

# Border (the "quiet zone" mandated by ISO/IEC 18004 §6.3.7) in modules.
# 4 is the standard minimum for a reliable scan.
_BORDER = 4


def svg_for_url(url: str) -> bytes:
    """Encode `url` as an SVG QR code and return the raw bytes.

    The output is byte-deterministic: the same URL produces identical bytes
    every call. Any change to the underlying `qrcode` library or to the
    constants in this module is a P1-PUB-impact change and requires a
    spec amendment + regenerated test baselines.
    """
    if not isinstance(url, str) or not url:
        raise ValueError("svg_for_url: url must be a non-empty string")

    qr = qrcode.QRCode(
        version=None,            # auto-size to the smallest version that fits
        error_correction=_ERROR_CORRECTION,
        box_size=_BOX_SIZE,
        border=_BORDER,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(image_factory=SvgPathImage)
    buf = BytesIO()
    img.save(buf)
    return buf.getvalue()


def svg_for_url_b64(url: str) -> str:
    """Base64-encoded SVG bytes for embedding in JSON responses.

    The encoding is `utf-8`-safe (SVG is text-based) but we still base64-wrap
    the bytes so callers can drop the value straight into an `<img src="data:...">`
    or a JSON field without escaping considerations.
    """
    return base64.b64encode(svg_for_url(url)).decode("ascii")
