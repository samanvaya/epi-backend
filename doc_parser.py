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
    "10": r"10\.\s+DATE\s+OF\s+REVISION.*"
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
    """
    Cleans text but respects HTML tags.
    Mammoth output is pretty clean but might have artifacts.
    """
    # Remove Likely Page Numbers if they appear in text (mammoth usually ignores headers/footers by default which is good!)
    # Mammoth converts standard body.
    
    # Just trim
    return text.strip()

def read_pdf(file_path: str) -> str:
    try:
        reader = pypdf.PdfReader(file_path)
        text = ""
        for page in reader.pages:
            extract = page.extract_text()
            if extract:
                text += extract + "\n"
        # Escape plain text to HTML-safe ? No, parser expects HTML logic now.
        # If we return plain text, the strategy must handle it.
        # But our strategy now expects HTML blocks.
        # Let's simple-escape the PDF text so it looks like HTML without tags
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
            # Custom Style Map:
            # 1. 'u => u': Maps underline formatting to <u> tags.
            # 2. 'r[style-name='Underline'] => u': Maps named character style "Underline".
            # 3. 'r[style-name='Hyperlink'] => u': Maps Hyperlink style to underline (optional diff visual).
            # 4. Header Demotion: h1->h3 etc. to avoid conflict with Section <h2>.
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
            html_output = result.value # The generated HTML
            messages = result.messages # Warnings
            
            # Post-process formatting if needed? 
            # Output is like: <p>...</p><table>...</table>
            # This is exactly what we need.
            return html_output
            
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
    """
    def __init__(self, headers: Dict[str, str]):
        self.headers = headers

    def parse(self, text: str) -> List[Dict[str, str]]:
        # text is HTML string.
        # We need to split it into "Visual Blocks" to scan for headers.
        # Mammoth returns compact HTML: <p>Heading</p><p>Content</p>
        # Unlike \n split, we should split by tags closing?
        # or just regex find the headers in the string?
        
        # Issue: <p>1. NAME</p>
        # If we use re.finditer on the whole string, we find index.
        # But we need to split *between* indices.
        
        # Let's try to map the whole string.
        # We strip tags to find indices. 
        # But indices in stripped string DO NOT match indices in HTML string.
        
        # Correct Approach for HTML:
        # Iterate over the HTML "Flow Elements" (p, table, ul, h1-h6).
        # This requires an HTML parser. 
        # We don't want to use BeautifulSoup (dependency).
        # We can loosely split by closing block tags like `</p>`, `</table>`, `</ul>`?
        
        # Heuristic Split: Split by `>` and check if it closes a block?
        # Or just split by regex `(</p>|</table>|</ul>|</li>|<br/>|<br>)`.
        
        # Let's use a "Block Splitter" regex.
        # Known blocks from mammoth: p, table, ul, ol.
        # We replace `</p>` with `</p>\n` temporarily to allow line splitting logic?
        
        # Add newlines after block closers if not present
        formatted_html = text.replace("</p>", "</p>\n") \
                             .replace("</table>", "</table>\n") \
                             .replace("</ul>", "</ul>\n") \
                             .replace("</ol>", "</ol>\n") \
                             .replace("</h1>", "</h1>\n") \
                             .replace("</h2>", "</h2>\n") \
                             .replace("</h3>", "</h3>\n") 
                             
        lines = formatted_html.split('\n')
        
        extracts = []
        current_section = None
        current_content = []
        
        # STATEFUL PARSING: Track if we are inside a table
        in_table = False
        
        def find_header(html_chunk, is_inside_table):
            # Optimization: Headers are almost always in <p>, <h1>-<h6> tags.
            # Strict Rule 1: Never treat a <table> or <ul>/<li> as a Header.
            if html_chunk.strip().startswith("<table") or html_chunk.strip().startswith("<li") or html_chunk.strip().startswith("<ul") or html_chunk.strip().startswith("<ol"):
                 return None, None

            # CRITICAL FIX for Tables:
            # If we are inside a table, we MUST NOT detect headers.
            # Otherwise, a row saying "4. Clinical..." will split the table.
            if is_inside_table:
                return None, None

            # Strip tags to check text content
            clean = re.sub(r'<[^>]+>', '', html_chunk).strip()
            # Canonicalize spaces
            clean = re.sub(r'\s+', ' ', clean)
            
            # Additional Safety: Headers shouldn't be excessively long.
            if len(clean) > 200: # heuristic
                return None, None
            
            for sec_id, ptrn in self.headers.items():
                # Allow match at start of clean text
                if re.search(ptrn, clean, re.IGNORECASE): 
                     return sec_id, clean
            return None, None
            
        for line in lines:
            if not line.strip(): continue
            
            # Update Table State
            # Simple check: <table or </table>
            # Note: A line might contain BOTH if the table is small and on one line?
            # Mammoth usually pretty prints but let's be careful.
            # If <table... is in line, we enter table mode.
            if "<table" in line:
                in_table = True
            
            # Check for header
            sec_id, title = find_header(line, in_table)
            
            # Update Table State (End)
            # If </table> is in line, we exit table mode AFTER processing this line 
            # (matches are done above, so we don't start a header on the closing line ideally, 
            # unless the header IS the closing line? unlikely).
            # Wait, if we are in_table=True, find_header returns None.
            # So if </table> is here, we are still technically in table for this line.
            # We exit AFTER.
            if "</table>" in line:
                in_table = False
            
            if sec_id:
                # New Section
                if current_section:
                    extracts.append({
                        "section_id": current_section['id'],
                        "title": current_section['title'],
                        "text": "".join(current_content).strip() # Join back to HTML string
                    })
                
                current_section = {'id': sec_id, 'title': title}
                current_content = [] 
                
                # Should we include the Header Line in the content?
                # Usually SmPC headers are NOT part of the body text.
                # So we skip adding `line` to `current_content`.
            else:
                if current_section:
                    current_content.append(line)
        
        if current_section:
             extracts.append({
                "section_id": current_section['id'],
                "title": current_section['title'],
                "text": "".join(current_content).strip()
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
        # text is HTML.
        # Logic: find keys in paragraphs.
        
        # Normalize structural newlines
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
            # Strip tags checking
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
                     current_content = [line] # Keep the HTML line containing key
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
        # Detect based on stripped content
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
