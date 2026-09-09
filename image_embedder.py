"""P1-IMG-1..4 — images from an uploaded DOCX become contained FHIR Binary
resources referenced from the narrative as ``<img src="#id" alt="…"/>``.

Where this sits in the pipeline
-------------------------------
``doc_parser.convert_image`` inlines every DOCX picture as a
``<img src="data:<mime>;base64,…">`` — that is the *parser-level intermediate*.
At mapping time (``fhir_mapper.create_doc_composition(…, embedder=…)``, before
Phase 1 validation) an ``ImageEmbedder`` rewrites each of those tags to
``<img src="#img-<sha256[:32]>" alt="…"/>`` and collects one ``BinaryRecord``
per distinct payload for ``Composition.contained``. The pattern follows the
EU IG (``EUEpiComposition.contained``: "Images in ePI Composition documents
included as contained binary resources"), the HL7 ePI Tech Style Guide
(https://build.fhir.org/ig/HL7/emedicinal-product-info/en/tech-style-guide.html#images)
and the EMA validated sample EPI-25-100.

Guarantees (FEATURE_SPEC.md §5 P1-IMG-1..4, CLAUDE.md §4.4, §5.5, §7.3, §9.3, §9.4)
------------------------------------------------------------------------------------
* Deterministic ids: ``id = "img-" + sha256(final bytes)[:32]``; identical bytes
  share one Binary. Same upload → same ids, same payload hashes.
* Idempotent: ``process(process(html)) == process(html)``; input without a
  ``data:`` image is returned byte-equal; already-rewritten ``#id`` tags are
  never touched and never re-audited.
* Nothing is ever dropped (ALCOA+ *Complete*): a payload that cannot be
  converted is kept with its real MIME type and flagged; a ``data:`` URI that
  cannot be decoded is left untouched and flagged.
* Every transformation is audited as an ``ImageAction`` (rule ids ``IMG-*``).
  ``main.py`` surfaces them in ``fix_log`` at ``iteration: 0``.
* No HTML parser is introduced — the codebase is regex-on-HTML throughout.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import logging
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# --- Constants ---------------------------------------------------------------

EXT_IMAGE_REFERENCE = "http://ema.europa.eu/fhir/StructureDefinition/ext-epi-image-reference"

# Binary.contentType values that are emitted as-is. Anything else is rasterised
# to PNG first (P1-IMG-2; CLAUDE.md §9.4).
WEB_SAFE_MIME = frozenset({"image/png", "image/jpeg", "image/svg+xml"})

BINARY_ID_PREFIX = "img-"

# Informational threshold only — no hard cap in v1 (FEATURE_SPEC §8 Q22).
MAX_IMAGE_BYTES_WARN = 1_048_576

# Formats Pillow cannot decode that LibreOffice Draw headless can rasterise.
LIBREOFFICE_MIME = frozenset({
    "image/x-emf", "image/emf", "image/x-wmf", "image/wmf",
    "application/x-msmetafile", "image/svg+xml",
})

# LibreOffice budget per *request* (all metafiles together), rasterisation
# target and size cap (FEATURE_SPEC §8 Q19 — pending Reg SME confirmation).
LIBREOFFICE_TIMEOUT_S = 15.0
LIBREOFFICE_DPI = 300
MAX_PNG_SIDE_PX = 2400

# Decompression-bomb guard: a few-KB TIFF/GIF can declare hundreds of
# megapixels. Checked from the header BEFORE decoding; anything larger is a
# flagged conversion failure, not an OOM-killed worker. 50 MP ≈ 7000×7000.
MAX_DECODE_PIXELS = 50_000_000

ALT_PLACEHOLDER_FMT = "Figure {n}"  # English in v1 (FEATURE_SPEC §8 Q20)

# Audit rule ids (CLAUDE.md §9.6).
RULE_EMBED = "IMG-EMBED"
RULE_RASTERISE = "IMG-RASTERISE"
RULE_ALT_MISSING = "IMG-ALT-MISSING"
RULE_FORMAT_UNSUPPORTED = "IMG-FORMAT-UNSUPPORTED"
RULE_SVG_UNSAFE = "IMG-SVG-UNSAFE"
RULE_SIZE_LARGE = "IMG-SIZE-LARGE"

_MIME_ALIASES = {
    "image/jpg": "image/jpeg",
    "image/pjpeg": "image/jpeg",
    "image/x-png": "image/png",
    "image/svg": "image/svg+xml",
    "image/x-ms-bmp": "image/bmp",
    "image/tif": "image/tiff",
}

_METAFILE_EXT = {
    "image/x-emf": "emf", "image/emf": "emf",
    "image/x-wmf": "wmf", "image/wmf": "wmf",
    "application/x-msmetafile": "emf",
    "image/svg+xml": "svg",
}

# --- Regexes -----------------------------------------------------------------

_IMG_TAG_RE = re.compile(r"<img\b([^>]*?)\s*/?>", re.IGNORECASE | re.DOTALL)
_ATTR_RE = re.compile(
    r"""([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.DOTALL
)
_DATA_URI_RE = re.compile(r"^data:([^;,]*)((?:;[^;,]*)*),(.*)$", re.DOTALL | re.IGNORECASE)

# SVG passes through untouched only if none of these match (P1-IMG-2).
_SVG_UNSAFE_PATTERNS = (
    re.compile(rb"<\s*script", re.IGNORECASE),
    re.compile(rb"\son[a-z]+\s*=", re.IGNORECASE),
    re.compile(rb"""(?:xlink:)?href\s*=\s*["']\s*(?!#|data:)""", re.IGNORECASE),
    re.compile(rb"""url\s*\(\s*["']?\s*(?!#|data:)""", re.IGNORECASE),
    re.compile(rb"<!ENTITY", re.IGNORECASE),
    re.compile(rb"<\s*foreignObject", re.IGNORECASE),
    re.compile(rb"@import", re.IGNORECASE),
)
# Constructs removed from an unsafe SVG before it is handed to the renderer
# (no scripts, handlers, external fetches or entity expansion reach LibreOffice).
_SVG_DEFANG = (
    (re.compile(rb"<\s*script\b.*?</\s*script\s*>", re.IGNORECASE | re.DOTALL), b""),
    (re.compile(rb"<\s*script\b[^>]*/?>", re.IGNORECASE), b""),
    (re.compile(rb"""\son[a-z]+\s*=\s*(?:"[^"]*"|'[^']*')""", re.IGNORECASE), b""),
    (re.compile(rb"""((?:xlink:)?href\s*=\s*["'])(?!#|data:)[^"']*(["'])""", re.IGNORECASE), rb"\1\2"),
    (re.compile(rb"""url\s*\(\s*["']?(?!#|data:)[^)]*\)""", re.IGNORECASE), b"none"),
    (re.compile(rb"<!ENTITY[^>]*>", re.IGNORECASE), b""),
    (re.compile(rb"<\s*foreignObject\b.*?</\s*foreignObject\s*>", re.IGNORECASE | re.DOTALL), b""),
    (re.compile(rb"@import[^;]*;", re.IGNORECASE), b""),
)


# --- Errors & records --------------------------------------------------------

class ImageConversionError(Exception):
    """Raised by a converter when a payload cannot be rasterised to PNG."""


@dataclass
class ImageAction:
    """One audited image transformation (same shape as a validator FixAction)."""
    rule: str
    location: str
    description: str
    before_snippet: str = ""
    after_snippet: str = ""


@dataclass
class BinaryRecord:
    """One ``Composition.contained`` Binary, in first-appearance document order."""
    id: str
    content_type: str
    data_b64: str
    byte_size: int
    sha256: str
    source_content_type: str


# --- Pure helpers -------------------------------------------------------------

def binary_id_for(data: bytes) -> str:
    """``"img-" + sha256(bytes)[:32]`` — FHIR id-safe (``[A-Za-z0-9\\-\\.]{1,64}``)."""
    return BINARY_ID_PREFIX + hashlib.sha256(data).hexdigest()[:32]


def normalise_mime(mime: str) -> str:
    m = (mime or "").strip().lower()
    return _MIME_ALIASES.get(m, m) or "application/octet-stream"


def tenant_is_allowlisted(tenant_id: str) -> bool:
    """Per-tenant feature flag (CLAUDE.md §5.7), read exactly like
    ``PUBLICATION_TENANTS_ALLOWLIST`` in ``publication_service``. Default off."""
    raw = os.environ.get("IMAGE_BINARIES_TENANTS_ALLOWLIST", "")
    allowed = {t.strip() for t in raw.split(",") if t.strip()}
    return bool(tenant_id) and tenant_id in allowed


def _load_image(data: bytes):
    from PIL import Image
    im = Image.open(io.BytesIO(data))  # header only — nothing decoded yet
    if im.width * im.height > MAX_DECODE_PIXELS:
        raise ImageConversionError(
            f"image is {im.width}x{im.height} px (> {MAX_DECODE_PIXELS} px decode cap)")
    im.load()  # forces the decoder; multi-frame formats yield frame 0
    return im


def normalise_png(data: bytes) -> bytes:
    """Decode → re-save with fixed encoder settings and no ancillary text/time
    chunks, so the bytes are deterministic for a pinned Pillow version.

    Modes are preserved where PNG supports them (1/L/LA/RGB/RGBA); palette,
    CMYK, 16-bit and other modes are converted to RGB(A). An embedded ICC
    profile is carried over (ALCOA+ *Accurate*)."""
    try:
        im = _load_image(data)
    except Exception as exc:  # noqa: BLE001 — surfaced as a conversion error
        raise ImageConversionError(f"cannot decode image for PNG normalisation: {exc}") from exc
    if im.mode not in ("1", "L", "LA", "RGB", "RGBA"):
        has_alpha = "A" in im.mode or (im.mode == "P" and "transparency" in im.info)
        im = im.convert("RGBA" if has_alpha else "RGB")
    if im.mode in ("LA", "RGBA") and im.getchannel("A").getextrema() == (255, 255):
        im = im.convert(im.mode[:-1])  # fully opaque: drop the alpha channel (same pixels, fewer bytes)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=False, compress_level=6)
    return buf.getvalue()


def _cap_longest_side(png: bytes, max_side: int = MAX_PNG_SIDE_PX) -> bytes:
    im = _load_image(png)
    if max(im.size) <= max_side:
        return png
    from PIL import Image
    im.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=False, compress_level=6)
    return buf.getvalue()


def _metafile_size_mm(data: bytes, mime: str) -> Optional[tuple]:
    """Best-effort (width_mm, height_mm) from an EMF or placeable-WMF header.
    Returns None when the header is absent or implausible."""
    import struct
    try:
        if mime in ("image/x-emf", "image/emf", "application/x-msmetafile") and len(data) >= 40:
            rec_type, = struct.unpack_from("<I", data, 0)
            if rec_type == 1:  # EMR_HEADER
                l, t, r, b = struct.unpack_from("<iiii", data, 24)  # rclFrame, 0.01 mm
                w, h = (r - l) / 100.0, (b - t) / 100.0
                if 0 < w < 2000 and 0 < h < 2000:
                    return (w, h)
        if mime in ("image/x-wmf", "image/wmf") and len(data) >= 22:
            key, = struct.unpack_from("<I", data, 0)
            if key == 0x9AC6CDD7:  # placeable header
                _hmf, l, t, r, b, inch = struct.unpack_from("<HhhhhH", data, 4)
                if inch > 0:
                    w, h = (r - l) / inch * 25.4, (b - t) / inch * 25.4
                    if 0 < w < 2000 and 0 < h < 2000:
                        return (w, h)
    except Exception:  # noqa: BLE001 — sizing is best-effort only
        return None
    return None


def _libreoffice_to_png(data: bytes, mime: str, timeout: float = LIBREOFFICE_TIMEOUT_S) -> bytes:
    """Rasterise EMF/WMF/SVG with LibreOffice Draw headless.

    Private ``-env:UserInstallation`` per call (no profile-lock collisions under
    concurrency); the temp dir is removed in ``finally``. Output is sized for
    ``LIBREOFFICE_DPI`` from the metafile frame when it can be read, capped at
    ``MAX_PNG_SIDE_PX`` on the longest side, then ``normalise_png``-ed."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise ImageConversionError("LibreOffice (soffice) is not installed")
    if timeout <= 0:
        raise ImageConversionError("LibreOffice time budget for this request is exhausted")
    ext = _METAFILE_EXT.get(mime, "emf")
    work = tempfile.mkdtemp(prefix="lo-img-")
    try:
        src = os.path.join(work, f"in.{ext}")
        with open(src, "wb") as fh:
            fh.write(data)
        profile = os.path.join(work, "profile")
        convert_to = "png"
        size_mm = _metafile_size_mm(data, mime)
        if size_mm:
            w_px = int(round(size_mm[0] / 25.4 * LIBREOFFICE_DPI))
            h_px = int(round(size_mm[1] / 25.4 * LIBREOFFICE_DPI))
            scale = min(1.0, MAX_PNG_SIDE_PX / max(w_px, h_px, 1))
            w_px, h_px = max(1, int(w_px * scale)), max(1, int(h_px * scale))
            convert_to = (
                'png:draw_png_Export:{"PixelWidth":{"type":"long","value":"%d"},'
                '"PixelHeight":{"type":"long","value":"%d"}}' % (w_px, h_px)
            )
        cmd = [
            soffice, "--headless", "--norestore", "--nologo", "--nodefault",
            "--nolockcheck", f"-env:UserInstallation=file://{profile}",
            "--convert-to", convert_to, "--outdir", work, src,
        ]
        # start_new_session → the whole process group (oosplash + soffice.bin)
        # can be killed on timeout; otherwise soffice.bin outlives the wrapper.
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    start_new_session=True)
        except OSError as exc:
            raise ImageConversionError(f"LibreOffice could not be started: {exc}") from exc
        try:
            out_b, err_b = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
            proc.communicate()
            raise ImageConversionError(f"LibreOffice timed out after {timeout:.1f}s") from exc
        proc_returncode, proc_stderr, proc_stdout = proc.returncode, err_b, out_b
        out = os.path.join(work, "in.png")
        if not os.path.exists(out):
            tail = (proc_stderr or proc_stdout or b"")[-300:].decode("utf-8", "replace")
            raise ImageConversionError(f"LibreOffice produced no PNG (rc={proc_returncode}): {tail.strip()}")
        with open(out, "rb") as fh:
            png = fh.read()
        return normalise_png(_cap_longest_side(png))
    finally:
        shutil.rmtree(work, ignore_errors=True)


def to_png(data: bytes, mime: str, lo_timeout: float = LIBREOFFICE_TIMEOUT_S) -> bytes:
    """Default converter: Pillow first; LibreOffice for metafiles/SVG; otherwise
    ``ImageConversionError``. Always returns ``normalise_png``-ed bytes."""
    mime = normalise_mime(mime)
    try:
        return normalise_png(data)
    except ImageConversionError as pil_exc:
        if mime in LIBREOFFICE_MIME:
            return _libreoffice_to_png(data, mime, timeout=lo_timeout)
        raise ImageConversionError(f"unsupported image format {mime}: {pil_exc}") from pil_exc


def svg_is_safe(data: bytes) -> bool:
    """True when the SVG is plain UTF-8/ASCII text with no script, event
    handlers, external references, CSS imports or entity declarations.
    Compressed (svgz) or non-UTF-8 payloads cannot be inspected → unsafe."""
    if data[:2] == b"\x1f\x8b":
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return not any(p.search(data) for p in _SVG_UNSAFE_PATTERNS)


def defang_svg(data: bytes) -> bytes:
    """Strip the constructs `svg_is_safe` objects to, so an unsafe SVG can be
    rasterised without handing scripts / external fetches to the renderer."""
    for pattern, repl in _SVG_DEFANG:
        data = pattern.sub(repl, data)
    return data


def _xml_attr(value: str) -> str:
    """Escape a bare ``"`` (only possible from a single-quoted source attribute);
    everything else was already entity-escaped by the parser and is kept verbatim."""
    return value.replace('"', "&quot;")


# --- The embedder -------------------------------------------------------------

class ImageEmbedder:
    """Rewrites ``data:`` image URIs in narrative HTML to contained-Binary refs.

    Usage::

        emb = ImageEmbedder()
        html = emb.process(html, location="4.2")   # per section, document order
        emb.binaries   # -> [BinaryRecord, …] for Composition.contained
        emb.actions    # -> [ImageAction, …]  for fix_log (iteration 0)

    ``converter(data, mime) -> png_bytes`` may be injected for tests; it must
    raise ``ImageConversionError`` on failure. The default shares one
    ``LIBREOFFICE_TIMEOUT_S`` budget across every metafile in the request.
    """

    def __init__(self, converter: Optional[Callable[[bytes, str], bytes]] = None):
        self._converter = converter or self._default_convert
        self.binaries: List[BinaryRecord] = []
        self.actions: List[ImageAction] = []
        self._by_id: Dict[str, BinaryRecord] = {}
        self._figure_no = 0
        self._lo_seconds_used = 0.0
        self._untouched_seen: set = set()

    # -- converter with a shared LibreOffice budget --------------------------
    def _default_convert(self, data: bytes, mime: str) -> bytes:
        remaining = LIBREOFFICE_TIMEOUT_S - self._lo_seconds_used
        t0 = time.monotonic()
        try:
            return to_png(data, mime, lo_timeout=remaining)
        finally:
            if normalise_mime(mime) in LIBREOFFICE_MIME:
                self._lo_seconds_used += time.monotonic() - t0

    # -- public API ----------------------------------------------------------
    def process(self, html: str, location: str) -> str:
        """Rewrite every ``<img src="data:…">`` in ``html``; return the new HTML.
        Input without a ``data:`` image is returned byte-equal."""
        if not html or "<img" not in html.lower():
            return html
        return _IMG_TAG_RE.sub(lambda m: self._rewrite_tag(m, location), html)

    def fix_log_rows(self) -> List[dict]:
        """Actions as the four-key ``fix_log`` rows ``main.py`` emits (iteration 0)."""
        return [
            {"iteration": 0, "rule": a.rule, "description": a.description, "location": a.location}
            for a in self.actions
        ]

    # -- internals -------------------------------------------------------------
    def _log(self, rule: str, location: str, description: str, before: str = "", after: str = "") -> None:
        self.actions.append(ImageAction(rule, location, description, before, after))

    def _log_untouched(self, original: str, location: str, description: str) -> None:
        """IMG-FORMAT-UNSUPPORTED for a tag we leave in place — logged once per
        (location, tag) so re-processing the same text stays idempotent."""
        key = (location, hashlib.sha256(original.encode("utf-8")).hexdigest())
        if key in self._untouched_seen:
            return
        self._untouched_seen.add(key)
        self._log(RULE_FORMAT_UNSUPPORTED, location, description, before=original[:80])

    def _rewrite_tag(self, m: "re.Match[str]", location: str) -> str:
        original = m.group(0)
        attrs: Dict[str, str] = {}
        for name, dq, sq in _ATTR_RE.findall(m.group(1) or ""):
            attrs[name.lower()] = dq or sq  # whichever quote style matched ('' for alt="")
        src = attrs.get("src", "")
        if not src.lower().startswith("data:"):
            if "src" not in attrs and "data:" in (m.group(1) or "").lower():
                # unquoted src=data:… — cannot be parsed reliably; never guess.
                self._log_untouched(original, location,
                                    "inline image left untouched: unquoted data: src attribute")
            return original  # already ``#id`` (idempotent path) or non-inline image

        # Every inline image counts towards the "Figure N" ordinal, decodable
        # or not, so numbering follows the document's visual order.
        self._figure_no += 1
        figure_no = self._figure_no

        # -- decode the data: URI ------------------------------------------------
        dm = _DATA_URI_RE.match(src)
        if not dm or ";base64" not in dm.group(2).lower():
            self._log_untouched(original, location,
                                "inline image left untouched: data: URI is not base64-encoded")
            return original
        source_mime = normalise_mime(dm.group(1))
        try:
            data = base64.b64decode(re.sub(r"\s+", "", dm.group(3)), validate=True)
        except (binascii.Error, ValueError) as exc:
            self._log_untouched(original, location,
                                f"inline image left untouched: base64 payload is undecodable ({exc})")
            return original
        if not data:
            self._log_untouched(original, location,
                                "inline image left untouched: empty base64 payload")
            return original

        # -- choose the final bytes / MIME -------------------------------------------
        final, final_mime = self._finalise_payload(data, source_mime, location)

        # -- dedupe into the contained list -------------------------------------------
        bid = binary_id_for(final)
        dedup = bid in self._by_id
        if not dedup:
            rec = BinaryRecord(
                id=bid,
                content_type=final_mime,
                data_b64=base64.b64encode(final).decode("ascii"),
                byte_size=len(final),
                sha256=hashlib.sha256(final).hexdigest(),
                source_content_type=source_mime,
            )
            self._by_id[bid] = rec
            self.binaries.append(rec)
        rec = self._by_id[bid]
        self._log(
            RULE_EMBED, location,
            f"<img> #{figure_no} embedded as contained Binary {bid} "
            f"({final_mime}, {rec.byte_size} bytes, sha256={rec.sha256[:12]}, "
            f"dedup={'true' if dedup else 'false'})",
            before=f"src=data:{source_mime};base64,… ({len(data)} bytes)",
            after=f'src="#{bid}"',
        )

        # -- alt text (P1-IMG-3) --------------------------------------------------
        alt = attrs.get("alt", "")
        if alt is None or not alt.strip():
            alt = ALT_PLACEHOLDER_FMT.format(n=figure_no)
            self._log(
                RULE_ALT_MISSING, location,
                f'<img> #{figure_no} ({bid}) has no alt text; placeholder alt="{alt}" emitted — '
                "needs reviewer-supplied alt text (HL7 ePI Tech Style Guide § Images)",
                before='alt="" / absent', after=f'alt="{alt}"',
            )

        if not dedup and rec.byte_size > MAX_IMAGE_BYTES_WARN:
            self._log(
                RULE_SIZE_LARGE, location,
                f"Binary {bid} payload is {rec.byte_size} bytes (> {MAX_IMAGE_BYTES_WARN}); "
                "informational, no cap in v1 (FEATURE_SPEC §8 Q22)",
            )

        return f'<img src="#{bid}" alt="{_xml_attr(alt)}"/>'

    def _finalise_payload(self, data: bytes, source_mime: str, location: str):
        """Return ``(final_bytes, final_mime)`` applying P1-IMG-2 rules."""
        src_sha = hashlib.sha256(data).hexdigest()[:12]
        before = f"{source_mime} sha256={src_sha} bytes={len(data)}"

        if source_mime in ("image/png", "image/jpeg"):
            return data, source_mime  # web-safe: bytes pass through unchanged

        svg_unsafe = source_mime == "image/svg+xml" and not svg_is_safe(data)
        if source_mime == "image/svg+xml" and not svg_unsafe:
            return data, source_mime
        convert_input = data
        if svg_unsafe:
            convert_input = defang_svg(data)
            self._log(RULE_SVG_UNSAFE, location,
                      "SVG contains script / event handlers / external references / entities; "
                      "offending constructs stripped, then rasterising to PNG",
                      before=before)

        try:
            png = self._converter(convert_input, source_mime)
            if not isinstance(png, (bytes, bytearray)) or not png.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ImageConversionError("converter did not return PNG bytes")
            png = bytes(png)
        except ImageConversionError as exc:
            reason = str(exc)
        except Exception as exc:  # noqa: BLE001 — a converter must never break the request
            logger.exception("image converter failed for %s at %s", source_mime, location)
            reason = f"{exc.__class__.__name__}: {exc}"
        else:
            after = f"image/png sha256={hashlib.sha256(png).hexdigest()[:12]} bytes={len(png)}"
            self._log(RULE_RASTERISE, location,
                      f"rasterised {source_mime} -> image/png ({before} => {after})",
                      before=before, after=after)
            return png, "image/png"

        self._log(RULE_FORMAT_UNSUPPORTED, location,
                  f"could not convert {source_mime} to PNG ({reason}); original bytes preserved "
                  f"as Binary with contentType {source_mime} — review before submission",
                  before=before, after=before)
        return data, source_mime
