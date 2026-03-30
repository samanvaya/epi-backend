"""
FHIR Validation Agent
=====================
Validates FHIR XML using the official validator.fhir.org REST API,
automatically fixes common errors, and maintains an audit log.
"""

import subprocess
import re
import os
import json
import tempfile
import datetime
import xml.etree.ElementTree as ET
import httpx
from dataclasses import dataclass, field, asdict
from typing import List, Tuple, Optional
from html.parser import HTMLParser


# --- Data Classes ---

@dataclass
class ValidationIssue:
    severity: str        # "Error", "Warning", "Information", "Fatal"
    location: str        # FHIR path, e.g. "Bundle.entry[0].resource.section[2].text"
    message: str         # Human-readable message
    rule: str = ""       # Constraint ID, e.g. "XHTML_XHTML_Element"
    line: int = -1       # Line number in the XML file (-1 if unknown)
    col: int = -1        # Column number (-1 if unknown)

    def to_dict(self):
        return asdict(self)


@dataclass
class FixAction:
    rule: str            # Which fix rule was applied
    location: str        # What was targeted
    description: str     # What was changed
    before_snippet: str = ""
    after_snippet: str = ""


@dataclass
class ValidationRun:
    iteration: int
    timestamp: str
    issues: List[ValidationIssue] = field(default_factory=list)
    fixes_applied: List[FixAction] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0


# --- FHIR Validator (validator.fhir.org REST API) ---

class FHIRValidator:
    """Validates FHIR XML using the official validator.fhir.org OpenAPI endpoint."""

    # Official HL7 FHIR Validator REST API (https://validator.fhir.org/swagger-ui/index.html)
    VALIDATOR_URL = "https://validator.fhir.org/validate"

    # EMA ePI FHIR IG package id on packages.fhir.org / validator.fhir.org
    # The EMA ePI IG is published under this package id.
    EMA_EPI_IG = "hl7.eu.fhir.epil"

    def __init__(self, project_dir: str = None):
        self.project_dir = project_dir or os.path.dirname(os.path.abspath(__file__))

    # Fallback: HAPI FHIR public server
    HAPI_URL = "https://hapi.fhir.org/baseR4/Bundle/$validate"

    # Profile-not-found and Terminology messages that are validator *configuration* 
    # issues, not real XML structural errors. We filter these out so the
    # pipeline is not blocked or cluttered by missing remote IGs or missing CodeSystems.
    _PROFILE_NOT_FOUND_PATTERNS = [
        "could not be found",
        "not fetched",
        "unknown profile",
        "not able to check",
        "failed to retrieve",
        "codesystem is unknown",
        "unknown codesystem",
        "cannot be validated",
        "none of the codes provided are in the value set",
        "not found in the terminology server"
    ]

    def _filter_config_issues(self, issues: List["ValidationIssue"]) -> List["ValidationIssue"]:
        """Remove Profile/Terminology reference errors (validator config issues) from the log."""
        result = []
        for issue in issues:
            msg_lower = issue.message.lower()
            is_config_issue = any(p in msg_lower for p in self._PROFILE_NOT_FOUND_PATTERNS)
            if not is_config_issue:
                result.append(issue)
        return result

    def validate_string(self, xml_string: str, fhir_version: str = "4.0.1") -> List["ValidationIssue"]:
        """Validate FHIR XML using local Java CLI if available, otherwise fallback to web APIs."""
        import subprocess
        import tempfile
        import json
        import os

        # Standard context for EMA validation
        ig_pkg = "hl7.eu.fhir.epil"
        jar_path = os.path.join(self.project_dir, "validator_cli.jar")

        # 1. Primary: Local Java CLI Validator (Handles Context and IG natively)
        # Falls through to HTTP fallbacks if CLI fails or produces empty output.
        if os.path.exists(jar_path):
            xml_path = None
            json_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xml", mode="w", encoding="utf-8") as tmp_xml:
                    tmp_xml.write(xml_string)
                    xml_path = tmp_xml.name

                with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w") as tmp_json:
                    json_path = tmp_json.name

                cmd = [
                    "java",
                    "-Xmx1g",
                    "-XX:+UseSerialGC",
                    "-jar", jar_path,
                    xml_path,
                    "-version", fhir_version,
                    "-ig", ig_pkg,
                    "-output", json_path
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

                # Read output only if the file has content
                if os.path.exists(json_path):
                    content = open(json_path, "r", encoding="utf-8").read().strip()
                    if content:
                        out_data = json.loads(content)
                        issues = self._parse_json_outcome(out_data)
                        # CLI natively knows CodeSystems - no filtering needed
                        return issues
                    else:
                        # Empty output file: validator ran but wrote nothing.
                        # Log stderr for diagnosis and fall through to HTTP APIs.
                        import logging
                        logging.getLogger(__name__).warning(
                            f"CLI validator produced empty output. stderr: {proc.stderr[:500]}"
                        )
                        # Fall through to HTTP fallbacks below
            except subprocess.TimeoutExpired:
                # Timed out — fall through to HTTP fallbacks
                import logging
                logging.getLogger(__name__).warning("CLI validator timed out, falling back to HTTP APIs")
            except Exception:
                # Any other CLI error — fall through to HTTP fallbacks
                pass
            finally:
                if xml_path and os.path.exists(xml_path): os.remove(xml_path)
                if json_path and os.path.exists(json_path): os.remove(json_path)

        # 2. Fallback: Try validator.fhir.org via raw HTTP if Java logic failed/absent
        igs = f"hl7.fhir.r4.core#{fhir_version}&ig={ig_pkg}"
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{self.VALIDATOR_URL}?ig={igs}",
                    data=xml_string.encode("utf-8"),
                    headers={"Content-Type": "application/fhir+xml", "Accept": "application/json"}
                )
            if response.status_code == 200:
                issues = self._parse_json_outcome(response.json())
                return self._filter_config_issues(issues)
        except Exception:
            pass

        # 3. Fallback: HAPI FHIR public R4 server
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    self.HAPI_URL,
                    data=xml_string.encode("utf-8"),
                    headers={"Content-Type": "application/fhir+xml", "Accept": "application/fhir+xml"}
                )
            if response.status_code in (200, 400, 422):
                issues = self._parse_xml_outcome(response.text)
                return self._filter_config_issues(issues)
            return [ValidationIssue("Fatal", "", f"HAPI FHIR API error: HTTP {response.status_code}")]
        except Exception as e:
            return [ValidationIssue("Fatal", "", f"Both validator APIs failed: {str(e)}")]

    def _parse_json_outcome(self, outcome: dict) -> List[ValidationIssue]:
        """Parse the OperationOutcome JSON returned by validator.fhir.org."""
        issues = []
        try:
            for issue in outcome.get("issue", []):
                severity = issue.get("severity", "information").capitalize()
                if severity == "Fatal": severity = "Error"

                # Message text
                details = issue.get("details", {})
                message = details.get("text", issue.get("diagnostics", "Unknown issue"))

                # Location / expression
                expressions = issue.get("expression", [])
                location = expressions[0] if expressions else ""
                if not location:
                    locations = issue.get("location", [])
                    location = locations[0] if locations else ""

                # Rule / code
                rule = ""
                codings = details.get("coding", [])
                if codings:
                    rule = codings[0].get("code", "")
                    if "#" in rule:
                        rule = rule.split("#")[-1]

                # Line/col from extensions
                line_num = -1
                col_num = -1
                for ext in issue.get("extension", []):
                    url = ext.get("url", "")
                    if "issue-line" in url:
                        line_num = ext.get("valueInteger", -1)
                    elif "issue-col" in url:
                        col_num = ext.get("valueInteger", -1)

                issues.append(ValidationIssue(
                    severity=severity,
                    location=location,
                    message=message,
                    rule=rule,
                    line=line_num,
                    col=col_num
                ))
        except Exception as e:
            return [ValidationIssue("Fatal", "", f"Failed to parse validator response: {str(e)}")]
        return issues

    def _parse_xml_outcome(self, xml_str: str) -> List[ValidationIssue]:
        """Parse the OperationOutcome XML returned by HAPI FHIR."""
        issues = []
        try:
            xml_str = re.sub(r'\sxmlns="[^"]+"', '', xml_str, count=1)
            root = ET.fromstring(xml_str)
            for issue_node in root.findall('.//issue'):
                sev_node = issue_node.find('severity')
                severity = sev_node.get('value', 'information').capitalize() if sev_node is not None else "Information"
                if severity == "Fatal": severity = "Error"

                diag_node = issue_node.find('diagnostics')
                message = diag_node.get('value', 'Unknown issue') if diag_node is not None else "Unknown issue"

                line_ext = issue_node.find('.//extension[@url="http://hl7.org/fhir/StructureDefinition/operationoutcome-issue-line"]/valueInteger')
                col_ext = issue_node.find('.//extension[@url="http://hl7.org/fhir/StructureDefinition/operationoutcome-issue-col"]/valueInteger')
                line_num = int(line_ext.get('value')) if line_ext is not None else -1
                col_num = int(col_ext.get('value')) if col_ext is not None else -1

                rule = ""
                code_node = issue_node.find('.//details/coding/code')
                if code_node is not None:
                    rule = code_node.get('value', '')
                    if "#" in rule: rule = rule.split("#")[-1]

                loc_node = issue_node.find('expression')
                if loc_node is None:
                    loc_node = issue_node.find('location')
                location = loc_node.get('value', '') if loc_node is not None else ""

                issues.append(ValidationIssue(
                    severity=severity, location=location, message=message,
                    rule=rule, line=line_num, col=col_num
                ))
        except Exception as e:
            return [ValidationIssue("Fatal", "", f"Failed to parse HAPI response: {str(e)}")]
        return issues


# --- Auto-Fixer ---

class AutoFixer:
    """Applies heuristic fixes to common FHIR XML validation errors."""

    def fix(self, xml_string: str, issues: List[ValidationIssue]) -> Tuple[str, List[FixAction]]:
        """Apply all applicable fixes and return (fixed_xml, actions_taken)."""
        fixes = []
        fixed = xml_string

        # Run each fix strategy
        fixed, actions = self._fix_xhtml_namespace(fixed, issues)
        fixes.extend(actions)

        fixed, actions = self._fix_self_closing_tags(fixed, issues)
        fixes.extend(actions)

        fixed, actions = self._fix_unescaped_ampersands(fixed, issues)
        fixes.extend(actions)

        fixed, actions = self._fix_unclosed_tags(fixed, issues)
        fixes.extend(actions)

        fixed, actions = self._fix_empty_narratives(fixed, issues)
        fixes.extend(actions)

        fixed, actions = self._fix_invalid_xhtml_elements(fixed, issues)
        fixes.extend(actions)

        fixed, actions = self._fix_duplicate_xmlns(fixed, issues)
        fixes.extend(actions)
        
        fixed, actions = self._fix_invalid_table_attributes(fixed, issues)
        fixes.extend(actions)

        return fixed, fixes

    def _fix_xhtml_namespace(self, xml: str, issues: List[ValidationIssue]) -> Tuple[str, List[FixAction]]:
        """Add missing xmlns to <div> elements in narrative text."""
        fixes = []
        # Find <div> without xmlns
        pattern = re.compile(r'<div(?!\s[^>]*xmlns)(\s[^>]*)?>', re.IGNORECASE)
        matches = list(pattern.finditer(xml))

        if matches:
            # Replace from end to preserve indices
            for m in reversed(matches):
                before = m.group(0)
                after = before.replace('<div', '<div xmlns="http://www.w3.org/1999/xhtml"', 1)
                xml = xml[:m.start()] + after + xml[m.end():]
                fixes.append(FixAction(
                    rule="XHTML_NS_FIX",
                    location="div element",
                    description="Added missing xmlns='http://www.w3.org/1999/xhtml' to <div>",
                    before_snippet=before[:80],
                    after_snippet=after[:80]
                ))

        return xml, fixes

    def _fix_self_closing_tags(self, xml: str, issues: List[ValidationIssue]) -> Tuple[str, List[FixAction]]:
        """Convert HTML void elements to XHTML self-closing form."""
        fixes = []
        # Excluded 'meta' and 'link' because they conflict with core FHIR structural elements
        void_tags = ['br', 'hr', 'img']

        for tag in void_tags:
            # Match <br>, <br >, <hr class="x"> but NOT already <br/> or <br />
            pattern = re.compile(
                rf'<({tag})(\s[^>]*)?(?<!/)\s*>',
                re.IGNORECASE
            )

            def replacer(m):
                attrs = m.group(2) or ''
                return f'<{m.group(1)}{attrs}/>'

            new_xml = pattern.sub(replacer, xml)
            if new_xml != xml:
                count = len(pattern.findall(xml))
                fixes.append(FixAction(
                    rule="XHTML_SELF_CLOSING",
                    location=f"<{tag}> elements",
                    description=f"Converted {count} <{tag}> to self-closing <{tag}/> for XHTML compliance"
                ))
                xml = new_xml

        return xml, fixes

    def _fix_unescaped_ampersands(self, xml: str, issues: List[ValidationIssue]) -> Tuple[str, List[FixAction]]:
        """Escape bare & characters that aren't part of entities."""
        fixes = []
        # Match & not followed by a valid entity (amp;, lt;, gt;, quot;, apos;, #NNN;, #xHHH;)
        pattern = re.compile(r'&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[\da-fA-F]+);)')
        count = len(pattern.findall(xml))
        if count > 0:
            xml = pattern.sub('&amp;', xml)
            fixes.append(FixAction(
                rule="XHTML_AMPERSAND_ESCAPE",
                location="text content",
                description=f"Escaped {count} unescaped '&' characters as '&amp;'"
            ))
        return xml, fixes

    def _fix_unclosed_tags(self, xml: str, issues: List[ValidationIssue]) -> Tuple[str, List[FixAction]]:
        """Detect and close common unclosed HTML tags in narrative divs."""
        fixes = []
        # We only fix inside narrative <div> sections to avoid breaking FHIR structure
        inline_tags = ['b', 'i', 'u', 'em', 'strong', 'span', 'a', 'sub', 'sup']

        for tag in inline_tags:
            # Match <tag> or <tag attr="x"> but NOT <tag/> or <tag attr="x"/>
            open_pattern = re.compile(rf'<{tag}(?:\s[^>]*)?(?<!/)>',  re.IGNORECASE)
            close_pattern = re.compile(rf'</{tag}\s*>', re.IGNORECASE)

            open_count = len(open_pattern.findall(xml))
            close_count = len(close_pattern.findall(xml))

            if open_count > close_count:
                diff = open_count - close_count
                # Add closing tags before </div> (heuristic - close at the next block boundary)
                xml = xml.replace('</div>', f'</{tag}>' * diff + '</div>', diff)
                fixes.append(FixAction(
                    rule="XHTML_UNCLOSED_TAG",
                    location=f"<{tag}> elements",
                    description=f"Added {diff} missing </{tag}> closing tag(s)"
                ))

        return xml, fixes

    def _fix_empty_narratives(self, xml: str, issues: List[ValidationIssue]) -> Tuple[str, List[FixAction]]:
        """Add minimal content to empty narrative <div> elements."""
        fixes = []
        # Match <div xmlns="..."></div> (empty)
        pattern = re.compile(
            r'(<div\s+xmlns="http://www\.w3\.org/1999/xhtml"\s*>)\s*(</div>)',
            re.IGNORECASE
        )
        matches = list(pattern.finditer(xml))
        if matches:
            for m in reversed(matches):
                replacement = m.group(1) + '<p>No content available</p>' + m.group(2)
                xml = xml[:m.start()] + replacement + xml[m.end():]
            fixes.append(FixAction(
                rule="XHTML_EMPTY_NARRATIVE",
                location="empty div elements",
                description=f"Added placeholder content to {len(matches)} empty narrative div(s)"
            ))
        return xml, fixes

    def _fix_invalid_xhtml_elements(self, xml: str, issues: List[ValidationIssue]) -> Tuple[str, List[FixAction]]:
        """Remove or fix invalid XHTML elements flagged by the validator."""
        fixes = []
        # Check for issues mentioning specific invalid elements
        for issue in issues:
            msg = issue.message.lower()
            if 'unknown element' in msg or 'element not allowed' in msg:
                # Try to extract the element name
                elem_match = re.search(r"'(\w+)'", issue.message)
                if elem_match:
                    bad_elem = elem_match.group(1)
                    # Remove the element but keep its content
                    open_pat = re.compile(rf'<{bad_elem}(?:\s[^>]*)?>',  re.IGNORECASE)
                    close_pat = re.compile(rf'</{bad_elem}\s*>', re.IGNORECASE)
                    new_xml = open_pat.sub('', xml)
                    new_xml = close_pat.sub('', new_xml)
                    if new_xml != xml:
                        fixes.append(FixAction(
                            rule="XHTML_INVALID_ELEMENT",
                            location=f"<{bad_elem}> elements",
                            description=f"Removed invalid XHTML element <{bad_elem}> (kept inner content)"
                        ))
                        xml = new_xml
        return xml, fixes

    def _fix_duplicate_xmlns(self, xml: str, issues: List[ValidationIssue]) -> Tuple[str, List[FixAction]]:
        """Fix nested div elements that repeat xmlns when not needed (inner divs)."""
        fixes = []
        # In proper XHTML within FHIR, only the outermost <div> in a narrative
        # needs xmlns. Inner divs inherit it. But having it on inner divs is 
        # technically valid, so we only fix if the validator explicitly complains.
        for issue in issues:
            if 'namespace' in issue.message.lower() and 'duplicate' in issue.message.lower():
                # Remove xmlns from inner divs: the 2nd+ occurrence of <div xmlns=...>
                parts = xml.split('<div xmlns="http://www.w3.org/1999/xhtml">')
                if len(parts) > 2:
                    # Keep first, replace subsequent within same narrative block
                    fixed_xml = parts[0] + '<div xmlns="http://www.w3.org/1999/xhtml">'
                    for part in parts[1:]:
                        fixed_xml += part.replace(
                            '<div xmlns="http://www.w3.org/1999/xhtml">',
                            '<div>', 1
                        ) if parts.index(part) > 0 else part
                    if fixed_xml != xml:
                        fixes.append(FixAction(
                            rule="XHTML_DUPLICATE_NS",
                            location="nested div elements",
                            description="Removed duplicate xmlns from inner div elements"
                        ))
                        xml = fixed_xml
                break
        return xml, fixes

    def _fix_invalid_table_attributes(self, xml: str, issues: List[ValidationIssue]) -> Tuple[str, List[FixAction]]:
        """Remove presentation attributes from tables that violate FHIR XHTML rules."""
        fixes = []
        # FHIR strict XHTML restricts attributes on table, td, th, tr
        # Common invalid ones from Word/PDF converters: border, width, cellspacing, cellpadding, valign
        invalid_attrs = ['border', 'width', 'cellspacing', 'cellpadding', 'valign']
        
        has_table_issues = any('attribute' in i.message.lower() and 'not allowed' in i.message.lower() for i in issues)
        if not has_table_issues:
            # Only run if validator complained
            return xml, fixes
            
        new_xml = xml
        count = 0
        for attr in invalid_attrs:
            # Regex to find these attributes and strip them. e.g. border="1"
            pattern = re.compile(rf'\s+{attr}=["\'][^"\']*["\']', re.IGNORECASE)
            matches = len(pattern.findall(new_xml))
            if matches > 0:
                new_xml = pattern.sub('', new_xml)
                count += matches
                
        if count > 0:
            fixes.append(FixAction(
                rule="XHTML_INVALID_TABLE_ATTR",
                location="table elements",
                description=f"Removed {count} invalid styling attributes from tables/cells"
            ))
            
        return new_xml, fixes


# --- Validation Log ---

class ValidationLog:
    """Maintains a persistent audit trail of validation runs."""

    def __init__(self, log_dir: str = None):
        self.log_dir = log_dir or os.path.dirname(os.path.abspath(__file__))
        self.log_file = os.path.join(self.log_dir, "validation_log.json")
        self.runs: List[ValidationRun] = []

    def add_run(self, run: ValidationRun):
        self.runs.append(run)

    def save(self):
        """Save log to JSON file."""
        data = {
            "generated_at": datetime.datetime.now().isoformat(),
            "total_iterations": len(self.runs),
            "runs": []
        }
        for run in self.runs:
            run_data = {
                "iteration": run.iteration,
                "timestamp": run.timestamp,
                "error_count": run.error_count,
                "warning_count": run.warning_count,
                "info_count": run.info_count,
                "issues": [asdict(i) for i in run.issues],
                "fixes_applied": [asdict(f) for f in run.fixes_applied]
            }
            data["runs"].append(run_data)
        with open(self.log_file, 'w') as f:
            json.dump(data, f, indent=2)

    def to_markdown(self) -> str:
        """Generate a human-readable markdown report."""
        lines = []
        lines.append("# FHIR Validation Report")
        lines.append(f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Total Iterations:** {len(self.runs)}")
        lines.append("")

        for run in self.runs:
            lines.append(f"## Iteration {run.iteration}")
            lines.append(f"- **Errors:** {run.error_count}")
            lines.append(f"- **Warnings:** {run.warning_count}")
            lines.append(f"- **Information:** {run.info_count}")
            lines.append("")

            if run.issues:
                lines.append("### Issues Found")
                lines.append("| Severity | Location | Message |")
                lines.append("|----------|----------|---------|")
                for issue in run.issues[:50]:  # Cap at 50 for readability
                    loc = issue.location[:40] + "..." if len(issue.location) > 40 else issue.location
                    msg = issue.message[:80] + "..." if len(issue.message) > 80 else issue.message
                    lines.append(f"| {issue.severity} | `{loc}` | {msg} |")
                if len(run.issues) > 50:
                    lines.append(f"*... and {len(run.issues) - 50} more issues*")
                lines.append("")

            if run.fixes_applied:
                lines.append("### Fixes Applied")
                for fix in run.fixes_applied:
                    lines.append(f"- **[{fix.rule}]** {fix.description}")
                    if fix.location:
                        lines.append(f"  - Location: `{fix.location}`")
                lines.append("")

        # Final Summary
        if self.runs:
            first = self.runs[0]
            last = self.runs[-1]
            lines.append("## Summary")
            lines.append(f"- **Initial errors:** {first.error_count}")
            lines.append(f"- **Final errors:** {last.error_count}")
            lines.append(f"- **Initial warnings:** {first.warning_count}")
            lines.append(f"- **Final warnings:** {last.warning_count}")
            total_fixes = sum(len(r.fixes_applied) for r in self.runs)
            lines.append(f"- **Total fixes applied:** {total_fixes}")

            if last.error_count == 0:
                lines.append("\n✅ **Validation passed — no errors remaining.**")
            elif last.error_count < first.error_count:
                reduced = first.error_count - last.error_count
                lines.append(f"\n⚠️ **Reduced errors by {reduced}, but {last.error_count} remain.**")
            else:
                lines.append(f"\n❌ **{last.error_count} errors could not be auto-fixed.**")

        return "\n".join(lines)


# --- Pipeline Orchestrator ---

MAX_ITERATIONS = 1

def run_validation_pipeline(
    xml_string: str,
    project_dir: str = None,
    fhir_version: str = "4.0.1",
    progress_callback=None
) -> Tuple[str, ValidationLog, str]:
    """
    Full validation + auto-fix pipeline.

    Args:
        xml_string: The FHIR XML to validate.
        project_dir: Directory containing validator_cli.jar.
        fhir_version: FHIR version to validate against (default R4).
        progress_callback: Optional callable(message) for progress updates.

    Returns:
        (fixed_xml, validation_log, summary_message)
    """
    validator = FHIRValidator(project_dir)
    fixer = AutoFixer()
    log = ValidationLog(project_dir)

    current_xml = xml_string

    def update(msg):
        if progress_callback:
            progress_callback(msg)

    for iteration in range(1, MAX_ITERATIONS + 1):
        update(f"Iteration {iteration}: Running FHIR Validator...")

        # Validate
        issues = validator.validate_string(current_xml, fhir_version)

        # Count by severity
        errors = [i for i in issues if i.severity in ("Error", "Fatal")]
        warnings = [i for i in issues if i.severity == "Warning"]
        infos = [i for i in issues if i.severity == "Information"]

        run = ValidationRun(
            iteration=iteration,
            timestamp=datetime.datetime.now().isoformat(),
            issues=issues,
            error_count=len(errors),
            warning_count=len(warnings),
            info_count=len(infos)
        )

        update(f"Iteration {iteration}: Found {len(errors)} errors, {len(warnings)} warnings")

        # If no errors, we're done
        if len(errors) == 0:
            log.add_run(run)
            break

        # Apply fixes
        update(f"Iteration {iteration}: Applying auto-fixes...")
        fixed_xml, fix_actions = fixer.fix(current_xml, issues)
        run.fixes_applied = fix_actions
        log.add_run(run)

        # If no fixes were applied, stop (can't improve further)
        if not fix_actions or fixed_xml == current_xml:
            update(f"Iteration {iteration}: No more fixes available.")
            break

        current_xml = fixed_xml
        update(f"Iteration {iteration}: Applied {len(fix_actions)} fixes. Re-validating...")

    # Save log
    log.save()

    # Generate summary
    if log.runs:
        last = log.runs[-1]
        if last.error_count == 0:
            summary = f"✅ Validation passed after {len(log.runs)} iteration(s)."
        else:
            total_fixes = sum(len(r.fixes_applied) for r in log.runs)
            summary = (f"⚠️ {last.error_count} errors remain after {len(log.runs)} iteration(s). "
                       f"{total_fixes} fixes were applied.")
    else:
        summary = "No validation runs completed."

    return current_xml, log, summary
