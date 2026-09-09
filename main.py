from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
import hashlib
import os
import re
import json
import shutil
import logging
import tempfile
import uuid
from dataclasses import asdict

import doc_parser as parser
import fhir_mapper as mapper
import fhir_validator as validator
import diff_engine
# P1-PUB-1..4: opt-in publication / QR / render path. Imported at module load
# but inert until `publish: true` is sent on a request and the tenant is on
# `PUBLICATION_TENANTS_ALLOWLIST` (CLAUDE.md §5.7 per-tenant feature flag).
import publication_service as pub
# P1-IMG-1..4: DOCX images → Composition.contained Binary. Inert unless the
# tenant is on `IMAGE_BINARIES_TENANTS_ALLOWLIST` (CLAUDE.md §5.7, default off);
# flag-off output is byte-identical to v2.0.0.
import image_embedder as img

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

# Serve the canonical ePI stylesheet. The FHIR XHTML narrative contains NO
# inline font declarations — typography is supplied entirely by this CSS.
_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
CSS_HREF = "/static/epi-standard.css"


@app.post("/api/process_stateless")
def process_stateless(
    file: UploadFile = File(...),
    publish: bool = Form(False),
    tenant_id: str = Form(""),
):
    """
    Full ePI processing pipeline matching the Streamlit app functionality.
    Returns ALL data: validation runs, fix log, diff score, bundle JSON/XML,
    markdown report, and downloadable artifacts.

    Publication path (P1-PUB-1..4, opt-in, additive):
        publish=False or omitted (default)
            Behaviour and response shape are byte-identical to v2.0.0.
            The 21-field response in user story 8 is preserved.
        publish=True, status ∈ {"validated", "partially_fixed"}
            Two additive keys appear at the *end* of the response:
            `publication_id` (deterministic UUID v5 from tenant + bundle hash)
            and `qr_svg` (base64 SVG of the QR resolving to the render URL).
        publish=True, status == "errors"
            Returns HTTP 409 with code PUBLISH_REJECTED_INVALID_BUNDLE.
            Bright line: a non-conforming bundle is never published
            (CLAUDE.md §10 #12).
        publish=True, tenant not on PUBLICATION_TENANTS_ALLOWLIST
            Returns HTTP 403 with code PUBLICATION_FEATURE_DISABLED.
            Per-tenant feature flag default-off (CLAUDE.md §5.7).
    """
    try:
        logger.info(f"Received stateless request for file: {file.filename}")
        # P1-PUB-1: short-circuit when the caller asks to publish but is not
        # on the per-tenant allowlist. We reject before doing any parsing or
        # validator work so a non-allowlisted tenant cannot probe pipeline
        # behaviour by uploading varying inputs. This check fires ONLY when
        # `publish: true` is sent — the existing default-path is unchanged.
        if publish and not pub.tenant_is_allowlisted(tenant_id):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        f"publication is not enabled for tenant {tenant_id!r}; "
                        f"contact ops to be added to the "
                        f"PUBLICATION_TENANTS_ALLOWLIST"
                    ),
                    "code": "PUBLICATION_FEATURE_DISABLED",
                },
            )
        with tempfile.TemporaryDirectory() as temp_dir:
            safe_name = file.filename.replace(" ", "_")
            local_file_path = os.path.join(temp_dir, safe_name)
            # Stream-copy and compute the source SHA-256 in one pass. The
            # source hash — not the generated bundle hash — is what derives
            # publication_id. Reason: the FHIR mapper assigns new UUIDs on
            # every call, so two runs on the same DOCX produce different
            # bundle bytes and would break the P1-PUB-3 idempotency contract.
            # Hashing the upload bytes guarantees same-file → same-publication.
            _source_hasher = hashlib.sha256()
            with open(local_file_path, "wb") as buffer:
                while True:
                    chunk = file.file.read(64 * 1024)
                    if not chunk:
                        break
                    _source_hasher.update(chunk)
                    buffer.write(chunk)
            source_sha256 = _source_hasher.hexdigest()

            # 1. Parse document into sections
            sections = parser.parse_document(local_file_path, doc_type="Auto")

            if safe_name.endswith(".pdf"):
                raw_html = parser.read_pdf(local_file_path)
            else:
                raw_html = parser.read_docx(local_file_path)

            doc_type = parser.DocumentFactory.detect_type(raw_html)

            # Reject non-SmPC uploads: require at least two canonical SmPC top-level
            # section IDs (1-6 or well-known subsections) before running the pipeline.
            # Prevents meaningless 100% fidelity scores on documents that lack SmPC structure.
            _SMPC_ANCHOR_IDS = {"1", "2", "3", "4", "4.1", "4.2", "4.3", "4.4", "4.8", "5", "6", "6.1"}
            found_anchors = {s.get("section_id", "") for s in sections} & _SMPC_ANCHOR_IDS
            if len(found_anchors) < 2:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Uploaded document does not appear to be an SmPC. "
                        f"Detected {len(found_anchors)} SmPC section anchor(s); need at least 2. "
                        f"Expected sections like '1. Name of the medicinal product', "
                        f"'4.1 Therapeutic indications', '4.8 Undesirable effects', etc."
                    ),
                )

            doc_obj = {
                "filename": file.filename,
                "type": doc_type,
                "sections": sections
            }

            # P1-IMG-4 feature flag, read next to the publish allowlist. When on,
            # one ImageEmbedder serves the whole request: it rewrites the
            # section text IN PLACE during create_doc_composition, so the
            # source_text built below and generate_bundle both see `#id`
            # references without a second embedding pass (idempotent no-op).
            embedder = img.ImageEmbedder() if img.tenant_is_allowlisted(tenant_id) else None

            # 2. Map single document to FHIR Composition XML
            comp = mapper.create_doc_composition(doc_obj, "urn:uuid:med-prod", "urn:uuid:org",
                                                 embedder=embedder)
            original_xml = mapper.resource_to_xml(comp)

            # Build source_text for fidelity scoring.
            # Rules:
            #   1. Skip _preface — lives in Composition.text metadata, not a numbered section
            #   2. Skip non-SmPC section IDs (labelling, annex variants) — not mapped to FHIR sections
            #   3. Skip duplicate section IDs — prevent word-count inflation from repeated IDs
            # labelling is now included — parser accumulates full Annex III content into it
            _NON_SMPC_IDS = {'annex_i', 'annex_ii', 'annex_iii'}
            source_parts = []
            seen_ids: set = set()
            for s in sections:
                sid = s.get('section_id', '')
                if sid == '_preface':
                    continue
                if sid in _NON_SMPC_IDS:
                    continue
                if sid in seen_ids:
                    continue
                seen_ids.add(sid)
                title = s.get('title', '').strip()
                text  = s.get('text',  '').strip()
                text_no_tags = re.sub(r'^\s*(<[^>]+>)+\s*', '', text)
                if title and (text.lower().startswith(title.lower())
                              or text_no_tags.lower().startswith(title.lower())):
                    source_parts.append(text)
                else:
                    source_parts.append(f"{title} {text}" if title else text)
            source_text = " ".join(source_parts)

            # 3. Run full validation + fidelity-improvement pipeline
            project_dir = os.path.dirname(os.path.abspath(__file__))
            fixed_xml, val_log, summary, fidelity_score = validator.run_validation_pipeline(
                original_xml,
                project_dir=project_dir,
                source_text=source_text,
            )

            last_run = val_log.runs[-1] if val_log.runs else None
            first_run = val_log.runs[0] if val_log.runs else None
            error_count = last_run.error_count if last_run else 0
            warning_count = last_run.warning_count if last_run else 0
            info_count = last_run.info_count if last_run else 0
            iterations = len(val_log.runs)

            validation_issues = [asdict(i) for i in (last_run.issues if last_run else [])]

            # Build fix log across all iterations. P1-IMG-4: image transforms
            # happened at mapping time, before Phase 1, so they lead the log
            # as `iteration: 0` rows with the same four keys as validator fixes.
            fix_log = embedder.fix_log_rows() if embedder is not None else []
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
            # P1-IMG-4 (ALCOA+ Complete): the downloadable log carries the
            # image transforms as an iteration-0 run WITH before/after
            # snippets (source MIME / sha256 / bytes), which the four-key
            # fix_log rows cannot hold. Flag-off: nothing is added.
            if embedder is not None and embedder.actions:
                val_log_data["runs"].append({
                    "iteration": 0,
                    "timestamp": "",
                    "error_count": 0,
                    "warning_count": 0,
                    "info_count": 0,
                    "issues": [],
                    "fixes_applied": [asdict(a) for a in embedder.actions],
                })
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

            # 4. Visual diff (fidelity_score already returned by the pipeline)
            try:
                diff_html = diff_engine.generate_html_diff(source_text, fixed_xml)
            except Exception:
                diff_html = ""

            # 5. Generate FHIR Bundle (JSON + XML) from this document
            bundle = mapper.generate_bundle([doc_obj], embedder=embedder)
            bundle_json = mapper.bundle_to_json(bundle)
            bundle_xml = mapper.bundle_to_xml(bundle)

            # Determine overall status
            if error_count == 0:
                status = "validated"
            elif first_run and error_count < first_run.error_count:
                status = "partially_fixed"
            else:
                status = "errors"

            # --- v2.0.0 baseline response (21 fields, public contract, frozen) ---
            response = {
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

                # Diff comparison.
                # Only surface the fidelity score when the XML is structurally
                # valid — otherwise the recall-based metric misleads users into
                # thinking an invalid document was processed successfully.
                "fidelity_score": fidelity_score if error_count == 0 else None,
                "fidelity_status": "available" if error_count == 0 else "suppressed_due_to_errors",
                "diff_html": diff_html,

                # Bundle
                "bundle_json": bundle_json,
                "bundle_xml": bundle_xml,

                # Source preview
                "source_text": source_text[:2000],
                "doc_type": doc_type,
                "sections_count": len(sections),

                # Static stylesheet contract — frontend/viewer should apply
                # this CSS to the XHTML narrative. The narrative itself
                # contains no inline font declarations.
                "css_href": CSS_HREF,
            }

            # --- P1-PUB: opt-in publication path. Strictly additive. ---
            # When `publish` is False (default) we return the baseline shape
            # untouched — byte-equivalent to v2.0.0 (CLAUDE.md §5.1).
            # The per-tenant allowlist check has already fired at the top
            # of the endpoint, before any parsing. Here we only enforce the
            # post-pipeline content guarantee.
            if publish:
                # Bright line: never publish a non-conforming bundle
                # (CLAUDE.md §10 #12).
                if status == "errors":
                    return JSONResponse(
                        status_code=409,
                        content={
                            "detail": "cannot publish a non-conforming bundle",
                            "code": "PUBLISH_REJECTED_INVALID_BUNDLE",
                            "error_count": error_count,
                        },
                    )
                # P1-PUB-3 idempotency key: hash the source upload, not the
                # bundle. See comment at the top of process_stateless for why.
                bundle_sha256 = source_sha256
                narrative_xhtml = _extract_narrative_xhtml(fixed_xml)
                # Single-language v1 (P2-PUB-LANG deferred).
                language = "en"
                correlation_id = str(uuid.uuid4())
                record = pub.publish_bundle(
                    tenant_id=tenant_id,
                    bundle_sha256=bundle_sha256,
                    xhtml=narrative_xhtml,
                    language=language,
                    validator_outcome=status,
                    fidelity_score=response["fidelity_score"],
                    correlation_id=correlation_id,
                    actor_id="system",  # FUTURE: replace with authenticated user
                )
                # Append the two additive fields at the *bottom* of the response
                # so client parsers that depend on order keep working
                # (CLAUDE.md §9.1).
                response["publication_id"] = record.publication_id
                response["qr_svg"] = record.qr_svg

            return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Stateless pipeline failed")
        raise HTTPException(status_code=500, detail=str(e))


# Pull every <text>...</text> narrative out of a FHIR Composition XML and
# concatenate them into a single XHTML fragment for storage + scan-time
# rendering. Pragmatic regex pass — robust enough for v1 demo. Future
# (P2-PUB-PROD): swap to fhir.resources XML parsing for fidelity.
_TEXT_NARRATIVE_RE = re.compile(
    r"<text\b[^>]*>(.*?)</text>", re.DOTALL | re.IGNORECASE
)


def _extract_narrative_xhtml(composition_xml: str) -> str:
    parts = _TEXT_NARRATIVE_RE.findall(composition_xml or "")
    if not parts:
        return (
            '<div xmlns="http://www.w3.org/1999/xhtml" class="epi-narrative">'
            'No human-readable narrative was generated for this bundle.</div>'
        )
    return (
        '<div xmlns="http://www.w3.org/1999/xhtml" class="epi-narrative">\n'
        + "\n".join(parts)
        + "\n</div>"
    )


@app.get("/api/v1/render/{publication_id}")
def render_publication(publication_id: str):
    """
    Public render endpoint for a previously-published bundle (P1-PUB-2).

    Unauthenticated by design (mixed-audience scan: patient / HCP / QA reviewer).
    Returns the rendered XHTML leaflet wrapped in a page chrome that links
    `/static/epi-standard.css`, declares the preview watermark required until
    P2-PUB-LANG and P2-PUB-PROD ship, and embeds an integrity-disclosure footer.

    Status codes:
        200  XHTML content served. content-type: application/xhtml+xml.
        404  publication_id is not in the store.
        410  publication_id has been revoked. body includes `revoked_at`.

    No transforms at scan time (CLAUDE.md §10 #9): the stored XHTML is served
    byte-for-byte.
    """
    record = pub.lookup(publication_id)
    if record is None:
        return JSONResponse(
            status_code=404,
            content={
                "detail": "publication not found",
                "code": "PUBLICATION_NOT_FOUND",
            },
        )
    if record.revoked_at is not None:
        return JSONResponse(
            status_code=410,
            content={
                "detail": "publication revoked",
                "code": "PUBLICATION_REVOKED",
                "revoked_at": record.revoked_at,
                "reason": record.revocation_reason,
            },
        )
    correlation_id = str(uuid.uuid4())
    pub.record_served(publication_id=publication_id, correlation_id=correlation_id)
    xhtml_page = pub.render_xhtml(record, css_href=CSS_HREF)
    return Response(
        content=xhtml_page,
        media_type="application/xhtml+xml; charset=utf-8",
        headers={"X-Correlation-Id": correlation_id},
    )


@app.get("/health")
def health_check():
    """Liveness probe for Render."""
    return {"status": "healthy"}
