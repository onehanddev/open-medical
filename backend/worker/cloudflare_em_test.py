import logging
import math
import sys
import requests
from config.get_env import cloudflare_acccount_id, cloudflare_api_token
import time
from db import SessionLocal
from sqlalchemy import select, update
from models import DocumentChunks

stories = [
  'This is a story about an orange cloud',
  'This is a story about a llama',
  'This is a story about a hugging emoji'
]



def cloudflare_embed(inputs):

    response = requests.post(
    f"https://api.cloudflare.com/client/v4/accounts/{cloudflare_acccount_id}/ai/run/@cf/baai/bge-m3",
    headers={"Authorization": f"Bearer {cloudflare_api_token}"},
    json={"text": inputs},
    timeout=(5, 60),
    )

    if not response.ok:
        print("Status:", response.status_code)
        print("Cloudflare error:", response.text)
    response.raise_for_status()

    body = response.json()
    if not body.get("success"):
        raise ValueError("Cloudflare reported an unsuccessful embedding request.")
    embeddings = body["result"]["data"]
    if not isinstance(embeddings, list) or len(embeddings) != len(inputs):
        raise ValueError("Cloudflare embedding count does not match input count.")
    for index, embedding in enumerate(embeddings):
        if (
            not isinstance(embedding, list)
            or len(embedding) != 1024
            or any(type(value) not in (int, float) or not math.isfinite(value)
                   for value in embedding)
        ):
            raise ValueError(f"Invalid Cloudflare embedding at batch index {index}; expected 1024 finite numbers.")
    return embeddings

def create_embeddings(chunks):

    BATCH_SIZE = 60

    all_embeddings = []

    for start in range(0, len(chunks), BATCH_SIZE):
        to_embed_chunks = chunks[start:start+BATCH_SIZE]
        doc_embeddings = cloudflare_embed(
            to_embed_chunks
        )
        all_embeddings.extend(doc_embeddings)
        print(

            f"Embedded {min(start + BATCH_SIZE, len(chunks))}/{len(chunks)} chunks"

        )
        if start + BATCH_SIZE < len(chunks):
            time.sleep(40)

    return all_embeddings

def get_all_chunks_from_db():
    # Copy scalar values so no ORM objects or transaction survive the read.
    with SessionLocal() as db:
        chunks = db.execute(
            select(DocumentChunks.id, DocumentChunks.content).order_by(DocumentChunks.id)
        ).all()

    if not chunks:
        logging.info("No chunks to embed.")
        return

    logging.info("Loaded %s chunks; database session closed before embedding.", len(chunks))
    all_embeddings = create_embeddings([chunk.content for chunk in chunks])
    if len(all_embeddings) != len(chunks):
        raise ValueError("Chunk/embedding count mismatch; no embeddings were saved.")

    # A fresh, atomic transaction avoids partial replacement on write failure.
    with SessionLocal.begin() as db:
        for chunk, embedding in zip(chunks, all_embeddings, strict=True):
            result = db.execute(
                update(DocumentChunks.__table__)
                .where(DocumentChunks.id == chunk.id, DocumentChunks.content == chunk.content)
                .values(embeddings=embedding)
            )
            if result.rowcount != 1:
                raise RuntimeError(
                    f"Chunk {chunk.id} was changed or deleted during embedding; rolling back all updates."
                )
    logging.info("Saved embeddings for %s chunks.", len(chunks))

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        get_all_chunks_from_db()
    except Exception:
        logging.exception("Cloudflare embedding update failed; exiting process.")
        sys.exit(1)
