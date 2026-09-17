import os
import requests
from config.get_env import cloudflare_acccount_id, cloudflare_api_token
import time
from db import SessionLocal
from sqlalchemy import select, insert
from models import DocumentChunks

stories = [
  'This is a story about an orange cloud',
  'This is a story about a llama',
  'This is a story about a hugging emoji'
]



def cloudflare_embed(inputs):
    print("cloudflare_acccount_id", cloudflare_acccount_id)
    print("cloudflare_api_token", cloudflare_api_token)

    response = requests.post(
    f"https://api.cloudflare.com/client/v4/accounts/{cloudflare_acccount_id}/ai/run/@cf/baai/bge-m3",
    headers={"Authorization": f"Bearer {cloudflare_api_token}"},
    json={"text": inputs}
    )

    response.raise_for_status()

    body = response.json()
    print("bodyyy",  body["result"]["data"])
    return body["result"]["data"]

def create_embeddings(chunks):

    BATCH_SIZE = 100

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
        time.sleep(40)

    return all_embeddings

def get_all_chunks_from_db():
    with SessionLocal() as db:
        try:
            contents = db.scalars(select(DocumentChunks.content)).all()
            print('contents', contents)
            all_embeddings = create_embeddings(contents)
            print('all embeddings', all_embeddings)
            chunks = db.scalars(select(DocumentChunks)).all()
            print('chunks', chunks)
            for chunk, embedding in zip(chunks, all_embeddings):
                chunk.embeddings = embedding

            db.commit()
            
        except Exception:
            db.rollback()
            raise

get_all_chunks_from_db()