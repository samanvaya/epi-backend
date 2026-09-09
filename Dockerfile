# Lightweight Python-only container — no Java required
FROM python:3.10-slim

# Install libmagic for file type detection and JRE/wget for FHIR Java Validator
RUN apt-get update && \
    apt-get install -y --no-install-recommends libmagic1 default-jre-headless wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# P1-IMG-2: LibreOffice Draw headless rasterises EMF/WMF -> PNG.
# Pinned via the Debian release in the base image; a base bump is an IMG-impact change.
RUN apt-get update && \
    apt-get install -y --no-install-recommends libreoffice-draw fonts-dejavu-core && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download HL7 FHIR Java Validator CLI
RUN wget -q -O validator_cli.jar https://github.com/hapifhir/org.hl7.fhir.core/releases/latest/download/validator_cli.jar

# Pre-fetch the EMA ePI Implementation Guide package to leverage Docker layer caching
# This command runs a dummy validation to force the package resolver to pull hl7.eu.fhir.epil
RUN touch dummy.xml && \
    echo "<Composition xmlns='http://hl7.org/fhir'><id value='1'/></Composition>" > dummy.xml && \
    java -Xmx1g -XX:+UseSerialGC -jar validator_cli.jar dummy.xml -version 4.0.1 -ig hl7.eu.fhir.epil || true && \
    rm dummy.xml

COPY main.py .
COPY doc_parser.py .
COPY fhir_mapper.py .
# P1-IMG-1..4: contained Binary embedding of DOCX images (flag-gated).
COPY image_embedder.py .
COPY fhir_validator.py .
COPY diff_engine.py .
COPY repair_engine.py .
# P1-PUB-1..4: opt-in publication / QR / render path. Inert until
# `publish: true` is sent on a request and the tenant is on
# PUBLICATION_TENANTS_ALLOWLIST. See CHANGELOG / FEATURE_SPEC §5.
COPY publication_service.py .
COPY qr_generator.py .
# Canonical 11pt Times New Roman stylesheet referenced by the
# `css_href` response field and the new render endpoint. (Was previously
# missing from the image; live prod returned 404 on /static/epi-standard.css.)
COPY static/ ./static/
# Runtime location for the v1-demo SQLite publication store. The dir is
# pre-created so the first publish call does not fail on a write to a
# non-existent directory. The DB itself is created on first use.
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
