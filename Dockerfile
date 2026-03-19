# Lightweight Python-only container — no Java required
FROM python:3.10-slim

# Install libmagic for file type detection
RUN apt-get update && \
    apt-get install -y --no-install-recommends libmagic1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY doc_parser.py .
COPY fhir_mapper.py .
COPY fhir_validator.py .
COPY diff_engine.py .
COPY repair_engine.py .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
