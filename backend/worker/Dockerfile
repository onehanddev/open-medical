# EKS / generic container for the worker. Build context is backend/worker.
FROM python:3.12-slim

WORKDIR /app

# Install deps first so code changes don't bust the pip layer.
COPY pyproject.toml README.md ./

# CPU-only torch: docling pulls CUDA torch by default (~4GB of nvidia/* + triton).
# Pre-installing from the PyTorch CPU index satisfies docling without CUDA.
RUN pip install --no-cache-dir \
      --index-url https://download.pytorch.org/whl/cpu \
      torch==2.14.0 torchvision==0.29.0 \
    && pip install --no-cache-dir .

# Copy runtime code only (see .dockerignore).
COPY s3_upload_fetch.py db.py models.py ./
COPY config/ ./config/

CMD ["python", "s3_upload_fetch.py"]
