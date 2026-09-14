# EKS / generic container for the worker. Build context is backend/worker.
FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir .

CMD ["python", "s3_upload_fetch.py"]
