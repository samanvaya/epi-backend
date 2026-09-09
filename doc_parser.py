import re
from typing import Dict, List, Optional, Any, Protocol
from abc import ABC, abstractmethod
import pypdf
import mammoth # New robust parser
import io
import logging
import os
import html
import base64
import zipfile
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

# --- Static Styling Contract ---
#
# All ePI output is rendered as 11pt Times New Roman via the global
# epi-standard.css stylesheet. The parser must NEVER pass through inline
# font-family, font-size, or color declarations from the source DOCX.
#
# The only `style` properties allowed to survive sanitization are layout
# primitives that carry real semantic meaning: text alignment (for
# paragraphs the author explicitly centered/right-aligned) and table
# geometry (borders, padding, width, border-collapse).
#
# Reference: HL7 ePI Tech Style Guide
# https://build.fhir.org/ig/HL7/emedicinal-product-info/en/tech-style-guide.html

_ALLOWED_STYLE_PROPS = {
    'text-align',
    'border', 'border-collapse', 'border-color', 'border-style',
    'border-width', 'border-top', 'border-right', 'border-bottom', 'border-left',
    'padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
    'width',
    'vertical-align',
}

_ALLOWED_TEXT_ALIGN_VALUES = {'center', 'right', 'justify'}

_ALLOWED_CLASS_NAMES = {'epi-annex-title', 'epi-narrative'}

_STRIPPED_PRESENTATION_ATTRS = ['face', 'color', 'size', 'bgcolor', 'align', 'valign']


def _sanitize_style_attr(style_value: str) -> str:
    """Return a re-composed style string containing ONLY whitelisted properties."""
    out = []
    for decl in style_value.split(';'):
        if ':' not in decl:
            continue
        prop, _, val = decl.partition(':')
        prop = prop.strip().lower()
        val = val.strip()
        if prop not in _ALLOWED_STYLE_PROPS:
            continue
        if prop == 'text-align' and val.lower() not in _ALLOWED_TEXT_ALIGN_VALUES:
            continue
        out.append(f"{prop}: {val}")
    return "; ".join(out)


def _sanitize_html_styles(html_str: str) -> str:
    """Strip inline fonts/colors/classes from HTML — keep only allowed layout styles.

    Aggressive by design: the document must render uniformly under the global
    11pt Times New Roman stylesheet. Any DOCX-derived font metadata is dropped.
    """
    if not html_str:
        return html_str

    # 1. Unwrap <font> tags (keep their contents, drop the tag and all its attrs).
    html_str = re.sub(r'<font\b[^>]*>', '', html_str, flags=re.IGNORECASE)
    html_str = re.sub(r'</font>', '', html_str, flags=re.IGNORECASE)

    # 2. Drop deprecated presentation attributes wherever they appear.
    for attr in _STRIPPED_PRESENTATION_ATTRS:
        html_str = re.sub(
            rf'\s+{attr}\s*=\s*"[^"]*"', '', html_str, flags=re.IGNORECASE
        )
        html_str = re.sub(
            rf"\s+{attr}\s*=\s*'[^']*'", '', html_str, flags=re.IGNORECASE
        )

    # 3. Rewrite every style="..." attribute through the whitelist.
    def _style_repl(m):
        sanitized = _sanitize_style_attr(m.group(1))
        return f'style="{sanitized}"' if sanitized else ''
    html_str = re.sub(
        r'style\s*=\s*"([^"]*)"', _style_repl, html_str, flags=re.IGNORECASE
    )
    html_str = re.sub(
        r"style\s*=\s*'([^']*)'", _style_repl, html_str, flags=re.IGNORECASE
    )

    # 4. Strip class attributes that aren't in the allowed set.
    def _class_repl(m):
        classes = [c for c in m.group(1).split() if c in _ALLOWED_CLASS_NAMES]
        return f'class="{" ".join(classes)}"' if classes else ''
    html_str = re.sub(
        r'class\s*=\s*"([^"]*)"', _class_repl, html_str, flags=re.IGNORECASE
    )
    html_str = re.sub(
        r"class\s*=\s*'([^']*)'", _class_repl, html_str, flags=re.IGNORECASE
    )

    # 5. Collapse dangling whitespace from stripped attributes.
    html_str = re.sub(r'\s{2,}(?=[>\s])', ' ', html_str)
    html_str = re.sub(r'<(\w+)\s+>', r'<\1>', html_str)

    return html_str


_ANNEX_LINE_RE = re.compile(
    r'^\s*ANNEX\s+[IVX]+\s*$',
    re.IGNORECASE,
)


def _elevate_annex_headers(html_str: str) -> str:
    """Wrap bare 'ANNEX I/II/III' lines in <h1 class="epi-annex-title">.

    Targets the text inside <p> elements whose visible content, stripped of
    tags, is exactly an annex roman-numeral marker. Idempotent — already
    elevated headings are left untouched.
    """
    if not html_str:
        return html_str

    def _p_repl(m):
        inner = m.group(1)
        visible = re.sub(r'<[^>]+>', '', inner).strip()
        if _ANNEX_LINE_RE.match(visible):
            return f'<h1 class="epi-annex-title">{visible.upper()}</h1>'
        return m.group(0)

    return re.sub(
        r'<p\b[^>]*>(.*?)</p>', _p_repl, html_str,
        flags=re.IGNORECASE | re.DOTALL,
    )

# --- Constants & Regex Definitions ---

SMPC_HEADERS = {
    "1": r"1\.\s+NAME\s+OF\s+THE\s+MEDICINAL\s+PRODUCT",
    "2": r"2\.\s+QUALITATIVE\s+AND\s+QUANTITATIVE\s+COMPOSITION",
    "3": r"3\.\s+PHARMACEUTICAL\s+FORM",
    "4": r"4\.\s+CLINICAL\s+PARTICULARS",
    "4.1": r"4\.1\s+Therapeutic\s+indications",
    "4.2": r"4\.2\s+Posology\s+and\s+method\s+of\s+administration",
    "4.3": r"4\.3\s+Contraindications",
    "4.4": r"4\.4\s+Special\s+warnings\s+and\s+precautions\s+for\s+use",
    "4.5": r"4\.5\s+Interaction\s+with\s+other\s+medicinal\s+products\s+and\s+other\s+forms\s+of\s+interaction",
    "4.6": r"4\.6\s+(Fertility,\s+|)pregnancy\s+and\s+lactation",
    "4.7": r"4\.7\s+Effects\s+on\s+ability\s+to\s+drive\s+and\s+use\s+machines",
    "4.8": r"4\.8\s+Undesirable\s+effects",
    "4.9": r"4\.9\s+Overdose",
    "5": r"5\.\s+PHARMACOLOGICAL\s+PROPERTIES",
    "5.1": r"5\.1\s+Pharmacodynamic\s+properties",
    "5.2": r"5\.2\s+Pharmacokinetic\s+properties",
    "5.3": r"5\.3\s+Preclinical\s+safety\s+data",
    "6": r"6\.\s+PHARMACEUTICAL\s+PARTICULARS",
    "6.1": r"6\.1\s+List\s+of\s+excipients",
    "6.2": r"6\.2\s+Incompatibilities",
    "6.3": r"6\.3\s+Shelf\s+life",
    "6.4": r"6\.4\s+Special\s+precautions\s+for\s+storage",
    "6.5": r"6\.5\s+Nature\s+and\s+contents\s+of\s+container",
    "6.6": r"6\.6\s+Special\s+precautions\s+for\s+disposal.*",
    "7": r"7\.\s+MARKETING\s+AUTHORISATION\s+HOLDER",
    "8": r"8\.\s+MARKETING\s+AUTHORISATION\s+NUMBER",
    "9": r"9\.\s+DATE\s+OF\s+FIRST\s+AUTHORISATION.*",
    "10": r"10\.\s+DATE\s+OF\s+REVISION.*",
    # Annex sections — critical for full-document fidelity
    "annex_i": r"ANNEX\s+I[\s\.:]+",
    "annex_ii": r"ANNEX\s+II[\s\.:]+",
    "annex_iii": r"ANNEX\s+III[\s\.:]+",
    "labelling": r"LABELLING",
}

PIL_HEADERS = {
    "1": r"1\.\s+What\s+.*\s+is\s+and\s+what\s+it\s+is\s+used\s+for",
    "2": r"2\.\s+What\s+you\s+need\s+to\s+know\s+before\s+you\s+(take|use)\s+.*",
    "3": r"3\.\s+How\s+to\s+(take|use)\s+.*",
    "4": r"4\.\s+Possible\s+side\s+effects",
    "5": r"5\.\s+How\s+to\s+store\s+.*",
    "6": r"6\.\s+Contents\s+of\s+the\s+pack\s+and\s+other\s+information"
}

# --- Helper Functions ---

def clean_text_preserving_html(text: str) -> str:
    return text.strip()

def read_pdf(file_path: str) -> str:
    try:
        reader = pypdf.PdfReader(file_path)
        text = ""
        for page in reader.pages:
            extract = page.extract_text()
            if extract:
                text += extract + "\n"
        escaped = html.escape(text).replace("\n", "<br/>")
        return _elevate_annex_headers(_sanitize_html_styles(escaped))
    except Exception as e:
        raise ValueError(f"Error reading PDF: {e}")

def convert_image(image):
    with image.open() as image_bytes:
        encoded = base64.b64encode(image_bytes.read()).decode("ascii")
    return {
        "src": f"data:{image.content_type};base64,{encoded}"
    }

# --- P0-3a: Word automatic numbering on QRD headings -------------------------
#
# Many MAH-authored SmPCs carry "1.", "4.1" … as Word *automatic numbering*
# (w:numPr resolved through numbering.xml), not as typed characters. mammoth
# drops automatic numbering, so those headings reach the section splitter as
# bare "Therapeutic indications" and match nothing — the P0-2 gate then 422s a
# valid SmPC. `_materialise_qrd_numbering` runs on the raw DOCX bytes before
# mammoth: it resolves every numbered paragraph's label and, ONLY where
# label + text matches an SmPC / PIL heading pattern (and the text is not
# already numbered), writes the label into the paragraph as literal text and
# cancels its numbering (numId 0) so mammoth emits a paragraph, not <ol><li>.
#
# Design constraints (FEATURE_SPEC §5 P0-3a; CLAUDE.md §5.8, §10):
#   * stdlib only; string surgery on document.xml — every other byte of the
#     DOCX is preserved, and a document that needs no change is returned
#     byte-identical;
#   * never invents a section: the resolved number must agree with the QRD
#     position (a "1." in front of CLINICAL PARTICULARS is left alone);
#   * never raises into the request — any failure logs and returns the input.

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_XML_NS = "http://www.w3.org/XML/1998/namespace"

# Header patterns that carry a number (Annex / Labelling markers have none).
_NUMBERED_HEADER_PATTERNS = [
    re.compile(ptn, re.IGNORECASE)
    for key, ptn in list(SMPC_HEADERS.items()) + list(PIL_HEADERS.items())
    if key not in ("annex_i", "annex_ii", "annex_iii", "labelling")
]


def _format_number(n: int, fmt: str) -> str:
    """Render counter `n` in a WordprocessingML numFmt (ST_NumberFormat)."""
    fmt = (fmt or "decimal")
    if fmt == "none":
        return ""
    if fmt == "decimalZero":
        return f"{n:02d}"
    if fmt in ("lowerLetter", "upperLetter"):
        if n <= 0:
            return ""
        # Word: a..z, then aa, bb, cc … (same letter repeated), not aa, ab.
        letter = chr(ord("a") + (n - 1) % 26) * ((n - 1) // 26 + 1)
        return letter.upper() if fmt == "upperLetter" else letter
    if fmt in ("lowerRoman", "upperRoman"):
        if n <= 0:
            return ""
        out, val = "", n
        for value, sym in ((1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
                           (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")):
            while val >= value:
                out += sym
                val -= value
        return out.upper() if fmt == "upperRoman" else out
    # decimal and every other (locale / ordinal) format: plain digits.
    return str(n)


class _WordNumbering:
    """Resolver for numbering.xml + styles.xml with Word's counter semantics."""

    def __init__(self, numbering_xml: Optional[bytes], styles_xml: Optional[bytes]):
        self.abstract: Dict[str, Dict[int, dict]] = {}   # abstractNumId -> ilvl -> level def
        self.nums: Dict[str, dict] = {}                   # numId -> {"aid", "overrides": {ilvl: start}}
        self.styles: Dict[str, dict] = {}                 # styleId -> {"basedOn", "numId", "ilvl"}
        self._counters: Dict[str, Dict[int, int]] = {}    # abstractNumId -> ilvl -> value
        self._overrides_applied: set = set()              # (numId, ilvl)
        if numbering_xml:
            self._parse_numbering(numbering_xml)
        if styles_xml:
            self._parse_styles(styles_xml)

    # -- parsing ---------------------------------------------------------------
    @staticmethod
    def _val(el, name: str, default=None):
        child = el.find(f"{{{_W_NS}}}{name}") if el is not None else None
        return child.get(f"{{{_W_NS}}}val", default) if child is not None else default

    def _parse_numbering(self, data: bytes) -> None:
        root = ET.fromstring(data)
        style_links: Dict[str, str] = {}
        for a in root.iter(f"{{{_W_NS}}}abstractNum"):
            aid = a.get(f"{{{_W_NS}}}abstractNumId")
            levels: Dict[int, dict] = {}
            for lvl in a.findall(f"{{{_W_NS}}}lvl"):
                parsed = self._parse_level(lvl)
                if parsed:
                    levels[parsed[0]] = parsed[1]
            self.abstract[aid] = levels
            link = self._val(a, "numStyleLink")
            if link:
                style_links[aid] = link
        for n in root.iter(f"{{{_W_NS}}}num"):
            nid = n.get(f"{{{_W_NS}}}numId")
            aid = self._val(n, "abstractNumId")
            overrides, level_overrides = {}, {}
            for ov in n.findall(f"{{{_W_NS}}}lvlOverride"):
                try:
                    ilvl = int(ov.get(f"{{{_W_NS}}}ilvl", "0"))
                    so = self._val(ov, "startOverride")
                    if so is not None:
                        overrides[ilvl] = int(so)
                except ValueError:
                    continue
                full = ov.find(f"{{{_W_NS}}}lvl")   # a complete level redefinition
                if full is not None:
                    parsed = self._parse_level(full, default_ilvl=ilvl)
                    if parsed:
                        level_overrides[ilvl] = parsed[1]
            self.nums[nid] = {"aid": aid, "overrides": overrides, "levels": level_overrides}
        self._style_links = style_links

    def _parse_level(self, lvl, default_ilvl: int = 0):
        try:
            ilvl = int(lvl.get(f"{{{_W_NS}}}ilvl", str(default_ilvl)))
            # ECMA-376 §17.9.25: an omitted w:start means 0 (Word always writes it).
            start = int(self._val(lvl, "start", "0"))
        except ValueError:
            return None
        restart = self._val(lvl, "lvlRestart")
        try:
            restart_val = int(restart) if restart is not None else None
        except ValueError:
            restart_val = None
        return ilvl, {
            "start": start,
            "fmt": self._val(lvl, "numFmt", "decimal"),
            "text": self._val(lvl, "lvlText", "%" + str(ilvl + 1) + "."),
            "legal": lvl.find(f"{{{_W_NS}}}isLgl") is not None,
            # lvlRestart: 0 → never restart; N → restart only when a level < N advances.
            "restart": restart_val,
        }

    def _parse_styles(self, data: bytes) -> None:
        root = ET.fromstring(data)
        for st in root.iter(f"{{{_W_NS}}}style"):
            sid = st.get(f"{{{_W_NS}}}styleId")
            if not sid:
                continue
            ppr = st.find(f"{{{_W_NS}}}pPr")
            numpr = ppr.find(f"{{{_W_NS}}}numPr") if ppr is not None else None
            self.styles[sid] = {
                "basedOn": self._val(st, "basedOn"),
                "numId": self._val(numpr, "numId") if numpr is not None else None,
                "ilvl": self._val(numpr, "ilvl") if numpr is not None else None,
            }

    # -- resolution ------------------------------------------------------------
    def style_numbering(self, style_id: Optional[str]):
        """(numId, ilvl) inherited from a paragraph style, walking basedOn."""
        seen, ilvl = set(), None
        while style_id and style_id not in seen and style_id in self.styles:
            seen.add(style_id)
            st = self.styles[style_id]
            if ilvl is None and st["ilvl"] is not None:
                ilvl = st["ilvl"]
            if st["numId"] is not None:
                return st["numId"], (ilvl if ilvl is not None else st["ilvl"])
            style_id = st["basedOn"]
        return None, None

    def _abstract_for(self, num_id: str, depth: int = 0):
        num = self.nums.get(num_id)
        if not num or depth > 5:
            return None, {}
        aid = num["aid"]
        link = getattr(self, "_style_links", {}).get(aid)
        if link:  # abstractNum defined via a numbering style → follow the style's num
            linked_num, _ = self.style_numbering(link)
            if linked_num and linked_num != num_id:
                laid, _ = self._abstract_for(linked_num, depth + 1)
                return laid, num["overrides"]
        return aid, num["overrides"]

    def next_label(self, num_id: Optional[str], ilvl: Optional[str]):
        """Advance the counters for one numbered paragraph.

        Returns (label, digits) — `label` rendered from lvlText, `digits` the
        dotted plain-decimal form used for QRD matching — or None when the
        paragraph is not numbered (numId 0 / unknown / bullet level)."""
        if not num_id or num_id == "0":
            return None
        aid, overrides = self._abstract_for(num_id)
        if aid is None or aid not in self.abstract:
            return None
        levels = dict(self.abstract[aid])
        levels.update(self.nums.get(num_id, {}).get("levels", {}))  # lvlOverride/lvl wins
        try:
            lvl = int(ilvl) if ilvl is not None else 0
        except ValueError:
            lvl = 0
        level = levels.get(lvl)
        if level is None or level["fmt"] == "bullet":
            return None
        counters = self._counters.setdefault(aid, {})
        if (num_id, lvl) not in self._overrides_applied and lvl in overrides:
            counters[lvl] = overrides[lvl] - 1
            self._overrides_applied.add((num_id, lvl))
        if lvl not in counters:
            counters[lvl] = level["start"] - 1
        counters[lvl] += 1
        for deeper in list(counters):
            if deeper <= lvl:
                continue
            restart = levels.get(deeper, {}).get("restart")
            if restart == 0 or (restart is not None and lvl >= restart):
                continue  # this level does not restart on the advance that just happened
            del counters[deeper]

        def value(k: int) -> int:
            return counters.get(k, levels.get(k, {}).get("start", 1))

        def render(m):
            k = int(m.group(1)) - 1
            fmt = "decimal" if level["legal"] else levels.get(k, {}).get("fmt", "decimal")
            return _format_number(value(k), fmt)

        label = re.sub(r"%(\d)", render, level["text"])
        digits = ".".join(str(value(k)) for k in range(lvl + 1))
        return label, digits


# Paragraph scanning is done on the raw XML string so untouched paragraphs are
# preserved byte-for-byte (ElementTree re-serialisation would rewrite the
# whole part). Nested paragraphs (text boxes) are handled with a depth stack.
def _scan_paragraphs(xml: str, w: str):
    """Yield (start, end, nested, children) for every paragraph in start order.

    `nested` is True for a paragraph inside another paragraph (text box);
    `children` lists the (start, end) spans of paragraphs directly or
    indirectly inside it, so callers can mask them without rescanning."""
    open_re = re.compile(rf"<{w}:p(?=[\s>/])[^>]*?(/?)>|</{w}:p>")
    spans, stack = [], []          # stack entries: [start, children]
    for m in open_re.finditer(xml):
        tag = m.group(0)
        if tag.startswith(f"</{w}:p"):
            if stack:
                start, children = stack.pop()
                span = (start, m.end(), bool(stack), children)
                spans.append(span)
                if stack:
                    stack[-1][1].append((start, m.end()))
        elif m.group(1) == "/":
            spans.append((m.start(), m.end(), bool(stack), []))
            if stack:
                stack[-1][1].append((m.start(), m.end()))
        else:
            stack.append([m.start(), []])
    spans.sort(key=lambda t: t[0])
    return spans


_MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"


def _ns_prefix(document_xml: str, uri: str) -> Optional[str]:
    m = re.search(r'xmlns:([A-Za-z0-9_.-]+)="' + re.escape(uri) + '"', document_xml)
    return m.group(1) if m else None


def _w_prefix(document_xml: str) -> Optional[str]:
    return _ns_prefix(document_xml, _W_NS)


def _materialise_qrd_numbering(docx_bytes: bytes) -> bytes:
    """See the P0-3a note above. Returns the input bytes unchanged when no
    QRD heading needs its number materialised, or on any failure."""
    try:
        return _materialise_qrd_numbering_impl(docx_bytes)
    except Exception as exc:  # noqa: BLE001 — never break the request
        logger.warning("P0-3a numbering pre-pass skipped: %s: %s", exc.__class__.__name__, exc)
        return docx_bytes


def _materialise_qrd_numbering_impl(docx_bytes: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as zin:
        names = zin.namelist()
        if "word/document.xml" not in names or "word/numbering.xml" not in names:
            return docx_bytes
        raw_doc = zin.read("word/document.xml")
        numbering_xml = zin.read("word/numbering.xml")
        styles_xml = zin.read("word/styles.xml") if "word/styles.xml" in names else None

    bom = b"\xef\xbb\xbf" if raw_doc.startswith(b"\xef\xbb\xbf") else b""
    xml = raw_doc[len(bom):].decode("utf-8")
    w = _w_prefix(xml)
    if not w or f"<{w}:numPr" not in xml and not styles_xml:
        return docx_bytes
    resolver = _WordNumbering(numbering_xml, styles_xml)
    if not resolver.nums:
        return docx_bytes

    ppr_re = re.compile(rf"^<{w}:p(?:\s[^>]*)?>\s*(<{w}:pPr>.*?</{w}:pPr>)", re.DOTALL)
    pprchange_re = re.compile(rf"<{w}:pPrChange\b.*?</{w}:pPrChange>", re.DOTALL)
    numpr_re = re.compile(rf"<{w}:numPr\b[^>]*?(?:/>|>.*?</{w}:numPr>)", re.DOTALL)
    val_re = lambda tag: re.compile(rf"<{w}:{tag}\b[^>]*?\b{w}:val=\"([^\"]*)\"[^>]*/?>")
    pstyle_re, numid_re, ilvl_re = val_re("pStyle"), val_re("numId"), val_re("ilvl")
    # Only a *container* <w:del>…</w:del> hides text; a self-closing <w:del/>
    # (deleted paragraph mark in rPr) must not swallow the following runs.
    del_re = re.compile(rf"<{w}:del\b[^>]*(?<!/)>.*?</{w}:del>", re.DOTALL)
    t_re = re.compile(rf"<{w}:t\b[^>]*?(?:/>|>(.*?)</{w}:t>)", re.DOTALL)
    tab_re = re.compile(rf"<{w}:tab\b[^>]*/>")
    run_re = re.compile(rf"<{w}:r\b[^>]*>.*?</{w}:r>", re.DOTALL)
    rpr_re = re.compile(rf"<{w}:rPr>.*?</{w}:rPr>", re.DOTALL)
    blank = lambda m: " " * len(m.group(0))

    # DrawingML text boxes carry the same content twice (mc:Choice + mc:Fallback);
    # Word and mammoth render one copy. Mask the fallback so counters advance once.
    scan_xml = xml
    mc = _ns_prefix(xml, _MC_NS)
    if mc and f"<{mc}:Fallback" in xml:
        scan_xml = re.compile(rf"<{mc}:Fallback\b.*?</{mc}:Fallback>", re.DOTALL).sub(blank, xml)

    spans = _scan_paragraphs(scan_xml, w)
    # QRD-order guard: within a heading family (SmPC / PIL) a materialised
    # number must advance the sequence, or restart at 1 (a leaflet following an
    # SmPC, a contents list followed by the real headings). Typed headings
    # advance the state too, so re-processing an already-materialised document
    # cannot promote a drifted body paragraph into a section.
    n_smpc = sum(1 for k in SMPC_HEADERS if k not in ("annex_i", "annex_ii", "annex_iii", "labelling"))
    last_seen: Dict[str, tuple] = {}
    lead_num_re = re.compile(r"^\s*(\d+(?:\.\d+)*)")

    def family_of(pattern_index: int) -> str:
        return "smpc" if pattern_index < n_smpc else "pil"

    def match_family(probe: str) -> Optional[str]:
        for i, pat in enumerate(_NUMBERED_HEADER_PATTERNS):
            if pat.match(probe):
                return family_of(i)
        return None

    def as_tuple(num: str) -> tuple:
        return tuple(int(x) for x in num.strip(".").split(".") if x.isdigit())

    def sequence_ok(fam: str, nums: tuple) -> bool:
        prev = last_seen.get(fam)
        if prev is None or nums == (1,):
            return True
        if fam == "pil":
            # A leaflet has exactly six flat sections, always present: strict succession.
            return len(nums) == 1 and nums[0] == prev[0] + 1
        # SmPC: forward only (a document may legitimately omit a sub-section).
        return nums > prev

    edits = []  # (start, end, new_paragraph_xml)
    for start, end, nested, children in spans:
        para = scan_xml[start:end]
        masked = pprchange_re.sub(blank, para)
        m_ppr = ppr_re.match(masked)
        ppr_eff = m_ppr.group(1) if m_ppr else ""
        m_num = numpr_re.search(ppr_eff)
        m_style = pstyle_re.search(ppr_eff)
        style_id = m_style.group(1) if m_style else None
        num_id = ilvl = None
        if m_num:
            block = m_num.group(0)
            m1, m2 = numid_re.search(block), ilvl_re.search(block)
            num_id = m1.group(1) if m1 else None
            ilvl = m2.group(1) if m2 else None
        if num_id is None:
            s_num, s_lvl = resolver.style_numbering(style_id)
            if s_num is None:
                continue
            num_id, ilvl = s_num, (ilvl if ilvl is not None else s_lvl)
        result = resolver.next_label(num_id, ilvl)   # counters advance even if we skip below
        if result is None:
            continue
        label, digits = result

        # Visible text of THIS paragraph: child paragraphs (text boxes), deleted
        # runs and run properties excluded; tabs become spaces.
        inner = masked
        for ns, ne in children:
            inner = inner[:ns - start] + " " * (ne - ns) + inner[ne - start:]
        inner = del_re.sub(blank, inner)
        inner = tab_re.sub(" ", inner)
        text = html.unescape("".join(t or "" for t in t_re.findall(inner)))
        text = re.sub(r"[\s\u00a0\u200b\u00ad]+", " ", text).strip()
        if not text:
            continue
        if lead_num_re.match(text):
            # Already numbered in the text: record its position for the order
            # guard, never inject a second number.
            fam = match_family(re.sub(r"\s+", " ", text))
            if fam:
                last_seen[fam] = as_tuple(lead_num_re.match(text).group(1))
            continue
        if nested:
            continue  # never edit a paragraph inside another paragraph (text box)

        # Candidates: the rendered label as-is, then the plain dotted form
        # ("4.1." / "(4)" / "4" → "4.1" / "4."), so lvlText quirks do not hide
        # a heading. The number must agree with the QRD position to be used.
        candidates = [label.strip(), digits if "." in digits else digits + "."]
        chosen = fam = None
        for cand in candidates:
            fam = match_family(re.sub(r"\s+", " ", f"{cand} {text}"))
            if fam:
                chosen = cand
                break
        if chosen is None or not sequence_ok(fam, as_tuple(chosen)):
            continue
        last_seen[fam] = as_tuple(chosen)

        # Build the replacement paragraph on the ORIGINAL bytes using offsets.
        # The label becomes the first text run (copying the first text run's
        # rPr so it looks like the heading); numbering is CANCELLED with
        # ilvl 0 / numId 0 rather than removed, so mammoth's style-linked
        # numbering fallback cannot turn the heading back into <ol><li>.
        rpr = ""
        for m_run in run_re.finditer(inner):
            if f"<{w}:t" in m_run.group(0):
                m_rpr = rpr_re.search(m_run.group(0))
                rpr = m_rpr.group(0) if m_rpr else ""
                break
        run = f'<{w}:r>{rpr}<{w}:t xml:space="preserve">{html.escape(chosen, quote=False)} </{w}:t></{w}:r>'
        cancel = f'<{w}:numPr><{w}:ilvl {w}:val="0"/><{w}:numId {w}:val="0"/></{w}:numPr>'
        para_orig = xml[start:end]
        if m_ppr:
            p0, p1 = m_ppr.start(1), m_ppr.end(1)          # pPr span within para
            ppr_orig = para_orig[p0:p1]
            if m_num:                                        # replace in place (keeps element order)
                new_ppr = ppr_orig[:m_num.start()] + cancel + ppr_orig[m_num.end():]
            elif m_style:                                    # style-numbered: cancel after pStyle
                new_ppr = ppr_orig[:m_style.end()] + cancel + ppr_orig[m_style.end():]
            else:
                open_len = len(f"<{w}:pPr>")
                new_ppr = ppr_orig[:open_len] + cancel + ppr_orig[open_len:]
            new_para = para_orig[:p0] + new_ppr + run + para_orig[p1:]
        else:
            open_end = para_orig.index(">") + 1
            new_para = para_orig[:open_end] + f"<{w}:pPr>{cancel}</{w}:pPr>" + run + para_orig[open_end:]
        edits.append((start, end, new_para))

    if not edits:
        return docx_bytes
    for start, end, new_para in sorted(edits, reverse=True):
        xml = xml[:start] + new_para + xml[end:]
    new_doc = bom + xml.encode("utf-8")

    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as zin, zipfile.ZipFile(out, "w") as zout:
        zout.comment = zin.comment
        for info in zin.infolist():
            data = new_doc if info.filename == "word/document.xml" else zin.read(info.filename)
            zout.writestr(info, data, compress_type=info.compress_type)
    return out.getvalue()


def read_docx(file_path: str) -> str:
    """
    Uses Mammoth to convert DOCX to strict HTML.
    Preserves: Tables, Images (Base64), Bold, lists, etc.
    """
    try:
        with open(file_path, "rb") as fh:
            docx_bytes = fh.read()
        # P0-3a: make Word automatic numbering on QRD headings visible to the
        # section splitter. Byte-level no-op for typed-number documents.
        docx_bytes = _materialise_qrd_numbering(docx_bytes)
        docx_file = io.BytesIO(docx_bytes)
        style_map = """
        u => u
        r[style-name='Underline'] => u
        r[style-name='Hyperlink'] => u
        p[style-name='Heading 1'] => h3:fresh
        p[style-name='Heading 2'] => h4:fresh
        p[style-name='Heading 3'] => h5:fresh
        p[style-name='Heading 4'] => h6:fresh
        """
        
        result = mammoth.convert_to_html(
            docx_file,
            style_map=style_map,
            convert_image=mammoth.images.img_element(convert_image)
        )
        html_out = result.value

        # Enforce the static-styling contract: strip DOCX font metadata
        # and elevate bare "ANNEX I/II/III" paragraphs to semantic h1s.
        html_out = _sanitize_html_styles(html_out)
        html_out = _elevate_annex_headers(html_out)
        return html_out

    except Exception as e:
        print(f"Mammoth conversion failed: {e}")
        raise e

# --- Strategy Pattern ---

class ParsingStrategy(ABC):
    @abstractmethod
    def parse(self, text: str) -> List[Dict[str, str]]:
        pass

class RegexStrategy(ParsingStrategy):
    """
    Parses HTML content by finding Headers (ignoring tags during search)
    and aggregating HTML blocks between them.
    Captures preface content (before section 1) into a dedicated bucket.
    """
    def __init__(self, headers: Dict[str, str]):
        self.headers = headers

    def parse(self, text: str) -> List[Dict[str, str]]:
        # Add newlines after block closers for line-based processing
        formatted_html = text \
            .replace("</p>", "</p>\n") \
            .replace("</table>", "</table>\n") \
            .replace("</ul>", "</ul>\n") \
            .replace("</ol>", "</ol>\n") \
            .replace("</h1>", "</h1>\n") \
            .replace("</h2>", "</h2>\n") \
            .replace("</h3>", "</h3>\n") \
            .replace("</h4>", "</h4>\n") \
            .replace("</h5>", "</h5>\n") \
            .replace("</h6>", "</h6>\n")

        lines = formatted_html.split('\n')
        
        extracts = []
        current_section = None
        current_content = []
        # Preface: content before the first matched section header
        preface_content = []
        found_first_section = False
        
        # Stateful tracking
        in_table = False
        in_list = False  # FIX: track list state to avoid splitting lists
        # Once we enter an annex/labelling section, stop matching new headers so all
        # subsequent content accumulates into that section (avoids duplicate section IDs
        # and preserves Annex III labelling content intact).
        _ANNEX_IDS = {'labelling', 'annex_i', 'annex_ii', 'annex_iii'}
        in_annex = False

        def find_header(html_chunk, is_inside_table, is_inside_list, is_inside_annex):
            # Never treat table/list/annex content as a header
            stripped = html_chunk.strip()
            if stripped.startswith("<table") or stripped.startswith("<li") \
               or stripped.startswith("<ul") or stripped.startswith("<ol"):
                return None, None

            # Critical: never match headers inside tables, lists, or annex blocks
            if is_inside_table or is_inside_list or is_inside_annex:
                return None, None

            # Strip tags to check text content
            clean = re.sub(r'<[^>]+>', '', html_chunk).strip()
            clean = re.sub(r'\s+', ' ', clean)

            # Headers are short by definition
            if len(clean) > 200:
                return None, None

            for sec_id, ptrn in self.headers.items():
                if re.search(ptrn, clean, re.IGNORECASE):
                    return sec_id, clean
            return None, None

        for line in lines:
            if not line.strip():
                continue

            # --- Update structural state BEFORE processing ---
            if "<table" in line:
                in_table = True
            if "<ul" in line or "<ol" in line:
                in_list = True

            # Check for a section header
            sec_id, title = find_header(line, in_table, in_list, in_annex)

            # --- Update structural state AFTER header check ---
            if "</table>" in line:
                in_table = False
            if "</ul>" in line or "</ol>" in line:
                in_list = False

            if sec_id:
                found_first_section = True
                # Save the previous section (or finalize preface)
                if current_section:
                    extracts.append({
                        "section_id": current_section['id'],
                        "title": current_section['title'],
                        "text": "".join(current_content).strip()
                    })

                # Once we enter an annex/labelling section, lock into it so all
                # subsequent numbered sub-items are content, not new sections.
                if sec_id in _ANNEX_IDS:
                    in_annex = True

                current_section = {'id': sec_id, 'title': title}
                current_content = []
            else:
                if current_section:
                    current_content.append(line)
                elif not found_first_section:
                    # Accumulate into preface bucket (Option B: goes to Composition root narrative)
                    preface_content.append(line)
        
        # Finalize last section
        if current_section:
            extracts.append({
                "section_id": current_section['id'],
                "title": current_section['title'],
                "text": "".join(current_content).strip()
            })
        
        # Inject preface as a special section with id "_preface"
        # fhir_mapper will merge this into Composition.text.div (Option B — FHIR compliant)
        preface_text = "".join(preface_content).strip()
        if preface_text:
            extracts.insert(0, {
                "section_id": "_preface",
                "title": "Preface",
                "text": preface_text
            })
             
        return extracts

class SmPCStrategy(RegexStrategy):
    def __init__(self):
        super().__init__(SMPC_HEADERS)

class PILStrategy(RegexStrategy):
    def __init__(self):
        super().__init__(PIL_HEADERS)

class LabellingStrategy(ParsingStrategy):
    def parse(self, text: str) -> List[Dict[str, str]]:
        formatted_html = text.replace("</p>", "</p>\n") \
                             .replace("</table>", "</table>\n") \
                             .replace("</ul>", "</ul>\n") \
                             .replace("</ol>", "</ol>\n") \
                             .replace("</h1>", "</h1>\n") \
                             .replace("</h2>", "</h2>\n") \
                             .replace("<br />", "\n").replace("<br/>", "\n")

        lines = formatted_html.split('\n')
        extracts = []
        keys = ["EXPIRY DATE", "BATCH NUMBER", "METHOD OF ADMINISTRATION", "NAME OF THE MEDICINAL PRODUCT"]
        
        current_key = None
        current_content = []
        
        for line in lines:
            clean = re.sub(r'<[^>]+>', '', line).strip()
            clean_upper = clean.upper()
            
            is_key = False
            for k in keys:
                if clean_upper.startswith(k):
                    if current_key:
                        extracts.append({
                            "section_id": "L_" + current_key.replace(" ", "_"),
                            "title": current_key,
                            "text": "".join(current_content).strip()
                        })
                    current_key = k
                    current_content = [line]
                    is_key = True
                    break
            
            if not is_key and current_key:
                current_content.append(line)

        if current_key:
            extracts.append({
                "section_id": "L_" + current_key.replace(" ", "_"),
                "title": current_key,
                "text": "".join(current_content).strip()
            })
        return extracts

# --- Factory ---

class DocumentFactory:
    @staticmethod
    def get_strategy(doc_type: str) -> ParsingStrategy:
        if doc_type == "SmPC": return SmPCStrategy()
        elif doc_type == "PIL": return PILStrategy()
        elif doc_type == "Labelling": return LabellingStrategy()
        else: raise ValueError(f"Unknown document type: {doc_type}")

    @staticmethod
    def detect_type(text: str) -> str:
        clean = re.sub(r'<[^>]+>', '', text).upper()
        if "QUALITATIVE AND QUANTITATIVE COMPOSITION" in clean: return "SmPC"
        if "WHAT YOU NEED TO KNOW BEFORE YOU" in clean: return "PIL"
        if "EXPIRY DATE" in clean or "BATCH NUMBER" in clean: return "Labelling"
        return "SmPC"

def parse_document(file_path: str, doc_type: str = "Auto") -> List[Dict[str, str]]:
    if file_path.lower().endswith(".pdf"):
        text = read_pdf(file_path)
    elif file_path.lower().endswith(".docx"):
        text = read_docx(file_path)
    else:
        raise ValueError("Unsupported file format")
        
    if doc_type == "Auto":
        doc_type = DocumentFactory.detect_type(text)
        
    strategy = DocumentFactory.get_strategy(doc_type)
    return strategy.parse(text)
