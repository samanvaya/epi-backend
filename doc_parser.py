import re
from typing import Dict, List, Optional, Any, Protocol
from abc import ABC, abstractmethod
import pypdf
import mammoth # New robust parser
import os
import html
import base64

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
        return html.escape(text).replace("\n", "<br/>")
    except Exception as e:
        raise ValueError(f"Error reading PDF: {e}")

def convert_image(image):
    with image.open() as image_bytes:
        encoded = base64.b64encode(image_bytes.read()).decode("ascii")
    return {
        "src": f"data:{image.content_type};base64,{encoded}"
    }

def read_docx(file_path: str) -> str:
    """
    Uses Mammoth to convert DOCX to strict HTML.
    Preserves: Tables, Images (Base64), Bold, lists, etc.
    """
    try:
        with open(file_path, "rb") as docx_file:
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
            return result.value
            
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
