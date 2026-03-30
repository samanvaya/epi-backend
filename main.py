from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import shutil
import logging
import tempfile
import difflib
from dataclasses import asdict

import doc_parser as parser
import fhir_mapper as mapper
import fhir_validator as validator
import diff_engine

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ePI Processing Service",
    description="Full-featured ePI processing: parse, map to FHIR, validate & auto-fix, diff, bundle.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/process_stateless")
def process_stateless(file: UploadFile = File(...)):
    """
    Full ePI processing pipeline matching the Streamlit app functionality.
    Returns ALL data: validation runs, fix log, diff score, bundle JSON/XML,
    markdown report, and downloadable artifacts.
    """
    try:
        logger.info(f"Received stateless request for file: {file.filename}")
        with tempfile.TemporaryDirectory() as temp_dir:
            safe_name = file.filename.replace(" ", "_")
            local_file_path = os.path.join(temp_dir, safe_name)
            with open(local_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # 1. Parse document into sections
            sections = parser.parse_document(local_file_path, doc_type="Auto")

            if safe_name.endswith(".pdf"):
                raw_html = parser.read_pdf(local_file_path)
            else:
                raw_html = parser.read_docx(local_file_path)

            doc_type = parser.DocumentFactory.detect_type(raw_html)

            doc_obj = {
                "filename": file.filename,
                "type": doc_type,
                "sections": sections
            }

            # 2. Map single document to FHIR Composition XML
            comp = mapper.create_doc_composition(doc_obj, "urn:uuid:med-prod", "urn:uuid:org")
            original_xml = mapper.resource_to_xml(comp)

            # 3. Run full validation + auto-fix pipeline (up to 5 iterations)
            project_dir = os.path.dirname(os.path.abspath(__file__))
            fixed_xml, val_log, summary = validator.run_validation_pipeline(
                original_xml, project_dir=project_dir
            )

            last_run = val_log.runs[-1] if val_log.runs else None
            first_run = val_log.runs[0] if val_log.runs else None
            error_count = last_run.error_count if last_run else 0
            warning_count = last_run.warning_count if last_run else 0
            info_count = last_run.info_count if last_run else 0
            iterations = len(val_log.runs)

            validation_issues = [asdict(i) for i in (last_run.issues if last_run else [])]

            # Build fix log across all iterations
            fix_log = []
            for run in val_log.runs:
                for fix in run.fixes_applied:
                    fix_log.append({
                        "iteration": run.iteration,
                        "rule": fix.rule,
                        "description": fix.description,
                        "location": fix.location,
                    })

            # Validation log JSON
            val_log_data = {
                "generated_at": "",
                "total_iterations": iterations,
                "runs": []
            }
            for run in val_log.runs:
                val_log_data["runs"].append({
                    "iteration": run.iteration,
                    "timestamp": run.timestamp,
                    "error_count": run.error_count,
                    "warning_count": run.warning_count,
                    "info_count": run.info_count,
                    "issues": [asdict(i) for i in run.issues],
                    "fixes_applied": [asdict(f) for f in run.fixes_applied]
                })

            # Markdown report
            validation_report_md = val_log.to_markdown()

            # 4. Diff comparison: source text vs validated XML
            source_text = " ".join(f"{s['title']} {s['text']}" for s in sections)
            try:
                # Strip all XML/HTML tags for fidelity score — compare plain text only
                s_clean = diff_engine.clean_for_diff(source_text, preserve_formatting=False)
                t_clean = diff_engine.clean_for_diff(fixed_xml, preserve_formatting=False)
                matcher = difflib.SequenceMatcher(None, s_clean.split(), t_clean.split())
                fidelity_score = round(matcher.ratio() * 100, 1)
                # Visual diff still uses formatting for a WYSIWYG view
                diff_html = diff_engine.generate_html_diff(source_text, fixed_xml)
            except Exception:
                fidelity_score = 0.0
                diff_html = ""

            # 5. Generate FHIR Bundle (JSON + XML) from this document
            bundle = mapper.generate_bundle([doc_obj])
            bundle_json = mapper.bundle_to_json(bundle)
            bundle_xml = mapper.bundle_to_xml(bundle)

            # Determine overall status
            if error_count == 0:
                status = "validated"
            elif first_run and error_count < first_run.error_count:
                status = "partially_fixed"
            else:
                status = "errors"

            return {
                # Core fields for Supabase
                "status": status,
                "error_count": error_count,
                "warning_count": warning_count,
                "info_count": info_count,
                "summary": summary,
                "iterations": iterations,

                # XMLs
                "original_xml": original_xml,
                "xml": fixed_xml,               # validated/fixed XML

                # Validation issues (all runs via last run)
                "issues": validation_issues,

                # Fix log
                "fix_log": fix_log,

                # Downloadable artifacts as strings
                "validation_log_json": json.dumps(val_log_data, indent=2),
                "validation_report_md": validation_report_md,

                # Diff comparison
                "fidelity_score": fidelity_score,
                "diff_html": diff_html,

                # Bundle
                "bundle_json": bundle_json,
                "bundle_xml": bundle_xml,

                # Source preview
                "source_text": source_text[:2000],
                "doc_type": doc_type,
                "sections_count": len(sections),
            }

    except Exception as e:
        logger.exception("Stateless pipeline failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health_check():
    """Liveness probe for Render."""
    return {"status": "healthy"}
