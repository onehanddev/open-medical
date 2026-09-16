FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libxcb1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./

RUN pip install --no-cache-dir \
      --index-url https://download.pytorch.org/whl/cpu \
      torch==2.14.0 torchvision==0.29.0 \
    && pip install --no-cache-dir .

COPY s3_upload_fetch.py db.py models.py ./
COPY config/ ./config/

CMD ["python", "s3_upload_fetch.py"]