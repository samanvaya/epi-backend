import difflib
import re
import html

def clean_for_diff(text: str, preserve_formatting: bool = True) -> str:
    """
    Normalizes text for comparison.
    If preserve_formatting is True, keeps semantic tags: b, i, table, list structures.
    """
    if not text: return ""
    
    normalized = text
    
    # --- Pre-normalization: Structural equivalence fixes ---
    # Convert list items to bullet text so <li>text</li> matches "• text" from Word
    normalized = re.sub(r'<li[^>]*>\s*', '\u2022 ', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'</li>', '\n', normalized, flags=re.IGNORECASE)
    
    # Add space between adjacent table cells so text from col A and col B don't merge
    normalized = re.sub(r'</td>\s*<td', '</td> <td', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'</th>\s*<th', '</th> <th', normalized, flags=re.IGNORECASE)
    
    if preserve_formatting:
        # 1. Normalize synonymous tags
        normalized = normalized.replace("<strong>", "<b>").replace("</strong>", "</b>")
        normalized = normalized.replace("<em>", "<i>").replace("</em>", "</i>")
        
        # 2. Lowercase all tags for consistency
        normalized = re.sub(r'<[^>]+>', lambda m: m.group(0).lower(), normalized)
        
        # 3. Remove attributes from tags primarily, BUT preserve table layout attributes.
        # We want to keep colspan, rowspan, border for tables to render intelligibly.
        # Strategy: 
        # 1. Mask table tags? Or use a smarter regex.
        # 2. Or just don't strip attributes for table/td/th?
        
        def strip_attrs(match):
            tag = match.group(1)
            attrs = match.group(2)
            if tag in ['table', 'td', 'th', 'tr', 'thead', 'tbody']:
                # Keep colspan, rowspan. Strip styles/classes to reduce noise?
                # Actually, simplified: Extract colspan/rowspan if present
                kept_attrs = []
                for attr in ["colspan", "rowspan", "border"]:
                    # simplistic regex find
                    m_attr = re.search(fr'{attr}=["\'][^"\']*["\']', attrs)
                    if m_attr: kept_attrs.append(m_attr.group(0))
                
                return f"<{tag} {' '.join(kept_attrs)}>" if kept_attrs else f"<{tag}>"
            else:
                return f"<{tag}>"

        # Regex: <TAG (attributes)> 
        normalized = re.sub(r'<([a-z0-9]+)(\s+[^>]*)>', strip_attrs, normalized)
        
        # 4. Remove purely structural/meta tags we don't care about for "Content Format"
        # e.g. <div xmlns...>, <span>, <narrative>
        # We want to keep: p, br, b, i, u, table, tr, td, th, ul, ol, li, h1-h6
        # Easier to whitelist?
        
        def replace_tag(match):
            tag_full = match.group(0)
            tag_name = match.group(1)
            is_close = tag_full.startswith("</")
            
            # whitelist: p, br, b, strong, i, em, u, table elements, lists, and headers
            # INCLUDED: h1-h6 so that all structural headings are strictly compared for fidelity
            allowed = ["p", "br", "b", "strong", "i", "em", "u", "table", "tbody", "thead", "tr", "td", "th", "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6", "a"]
            
            if tag_name in allowed:
                return tag_full # Keep it
            else:
                return " " # Replace disallowed tags with space to avoid merging words
        
        # Regex for tags: </?([a-z0-9]+)...>
        normalized = re.sub(r'</?([a-z0-9]+)[^>]*>', replace_tag, normalized)
        
    else:
        # Strip all tags
        normalized = re.sub(r'<[^>]+>', ' ', normalized)

    # 5. Semantic Normalization for XML vs HTML compatibility
    # Normalize XHTML self-closing tags
    normalized = normalized.replace("<br/>", "<br>").replace("<hr/>", "<hr>")
    
    # Normalize spaces between tags. 
    # Valid XML pretty-print often adds newlines/spaces between block tags: </p> <p>.
    # Mammoth outputs </p><p>.
    # We want to treat them as identical.
    # Regex: Remove whitespace BETWEEN closing tag and opening tag?
    # Or just collapse all whitespace to single space, then remove space around tags?
    
    # Current flow:
    # 52: Collapse whitespace -> " "
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # 6. Remove spaces between tags
    # > < -> ><
    normalized = re.sub(r'>\s+<', '><', normalized)

    return normalized.strip()

def generate_html_diff(source_text: str, target_xml_content: str) -> str:
    """
    Generates a HTML diff visualization including formatting tags.
    """
    # 1. Prepare inputs with formatting preserved
    # We treat tags as "words" for the diff purpose?
    # Or strict char diff? Word diff is better for readability.
    # To treat tags as words, we ensure spaces around them?
    
    s_clean = clean_for_diff(source_text, preserve_formatting=True)
    t_clean = clean_for_diff(target_xml_content, preserve_formatting=True)
    
    # Pad tags with spaces so split() separates them
    s_clean = re.sub(r'(<[^>]+>)', r' \1 ', s_clean)
    t_clean = re.sub(r'(<[^>]+>)', r' \1 ', t_clean)
    
    source_words = s_clean.split()
    target_words = t_clean.split()
    
    matcher = difflib.SequenceMatcher(None, source_words, target_words)
    
    html_output = []
    
    for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
        if opcode == 'equal':
            segment = " ".join(source_words[a0:a1])
            # Render the checks as is? No, we want to DISPLAY the diff.
            # If we just put "<b>" in the output HTML, the browser renders bold.
            # That is what we want! "WYSIWYG" diff.
            html_output.append(f'<span class="diff-equal">{segment}</span>')
            
        elif opcode == 'insert':
            # Added in Target
            segment = " ".join(target_words[b0:b1])
            # If segment is "<b>", we want to show that BOLD was added.
            # Visualizing added formatting is hard if we render it.
            # Only textual content gets stylized by .diff-add.
            # But if we render the tag, the effect applies to valid range?
            html_output.append(f'<span class="diff-add">{segment}</span>')
            
        elif opcode == 'delete':
            # Missing in Target
            segment = " ".join(source_words[a0:a1])
            html_output.append(f'<span class="diff-del">{segment}</span>')
            
        elif opcode == 'replace':
            del_segment = " ".join(source_words[a0:a1])
            add_segment = " ".join(target_words[b0:b1])
            html_output.append(f'<span class="diff-del">{del_segment}</span>')
            html_output.append(f'<span class="diff-add">{add_segment}</span>')
            
    return " ".join(html_output)

def extract_content_from_xml(xml_str: str) -> str:
    return xml_str # Allow cleaning logic to handle it
