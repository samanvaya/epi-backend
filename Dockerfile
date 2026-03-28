# Lightweight Python-only container — no Java required
FROM python:3.10-slim

# Install libmagic for file type detection and JRE/wget for FHIR Java Validator
RUN apt-get update && \
    apt-get install -y --no-install-recommends libmagic1 default-jre-headless wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download HL7 FHIR Java Validator CLI
RUN wget -q -O validator_cli.jar https://github.com/hapifhir/org.hl7.fhir.core/releases/latest/download/validator_cli.jar

# Pre-fetch the EMA ePI Implementation Guide package to leverage Docker layer caching
# This command runs a dummy validation to force the package resolver to pull hl7.eu.fhir.epil
RUN touch dummy.xml && \
    echo "<Composition xmlns='http://hl7.org/fhir'><id value='1'/></Composition>" > dummy.xml && \
    java -Xmx300m -jar validator_cli.jar dummy.xml -version 4.0.1 -ig hl7.eu.fhir.epil || true && \
    rm dummy.xml

COPY main.py .
COPY doc_parser.py .
COPY fhir_mapper.py .
COPY fhir_validator.py .
COPY diff_engine.py .
COPY repair_engine.py .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
