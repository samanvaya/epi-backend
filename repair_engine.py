
import re
import html

def repair_section_content(section_text):
    """
    Fixes common HTML issues in section content.
    """
    # 1. Fix unclosed tables
    if section_text.count("<table") > section_text.count("</table>"):
        section_text += "</table>" * (section_text.count("<table") - section_text.count("</table>"))
    
    # 2. Remove empty paragraphs which often cause diff noise
    # section_text = re.sub(r'<p>\s*</p>', '', section_text) 
    # (Maybe too aggressive for strict fidelity, but good for "Clean" view)

    return section_text

def detect_and_fix_ghost_headers(sections):
    """
    Scans sections to see if a subsequent section's title is buried in the current section's text.
    Returns: (repaired_sections, logs)
    """
    logs = []
    # Map of ID -> expected title (simplified)
    # We can use the doc_parser.SMPC_HEADERS logic or heuristics
    
    # Heuristic: Check for "N. Title" pattern at end of text
    # This is complex to do blindly.
    # A safer approach for "Auto Repair" is to verify specific known pain points.
    
    # 1. Check Section 3 for "4. Clinical Particulars"
    # (Since we fixed the parser regex, this *shouldn't* happen, but this is the backup/repair)
    
    for i, sec in enumerate(sections):
        # Specific known ghost: Section 4 header in Section 3
        if sec['section_id'] == '3':
            if "4. CLINICAL PARTICULARS" in sec['text'].upper():
                # Finding the split point
                match = re.search(r'(<p>.*?4\.\s*CLINICAL PARTICULARS.*?</p>)', sec['text'], re.IGNORECASE | re.DOTALL)
                if match:
                    split_tag = match.group(1)
                    idx = sec['text'].find(split_tag)
                    
                    ghost_content = sec['text'][idx:]
                    clean_content = sec['text'][:idx]
                    
                    sec['text'] = clean_content
                    logs.append(f"Fixed Ghost Header: Removed '4. Clinical Particulars' from Section 3.")
                    
                    # We might want to append this content to Section 4 if Section 4 exists and is empty
                    # But usually Section 4 is a parent and text goes to 4.1 or stays in 4.
                    # Let's see if Section 4 exists
                    sec4 = next((s for s in sections if s['section_id'] == '4'), None)
                    if sec4:
                        if len(sec4['text']) < 10: # If empty-ish
                             # Actually usually the text is just the header.
                             pass
    
    return sections, logs

def run_intelligent_repair(doc_sections):
    """
    Main entry point for auto-repair.
    """
    logs = []
    
    # 1. Ghost Headers
    doc_sections, ghost_logs = detect_and_fix_ghost_headers(doc_sections)
    logs.extend(ghost_logs)
    
    # 2. Content Cleanup
    for sec in doc_sections:
        original = sec['text']
        repaired = repair_section_content(original)
        if repaired != original:
            sec['text'] = repaired
            logs.append(f"Fixed HTML structure (tables/tags) in Section {sec['section_id']}")
            
    return doc_sections, logs
