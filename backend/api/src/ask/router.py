from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from config.db import get_db
from config.get_env import (
    jina_api_key as JINA_API_KEY,
    cloudfront_base_url,
    cloudfront_key_pair_id,
    cloudfront_private_key,
    cloudfront_url_expiration,
)
import requests
from models import DocumentChunks
from schema.ask import AskPostRequest
from utils.llm import build_context, generate_answer
from utils.cloudfront_signer import create_policy, sign_policy, cloudfront_base64

router = APIRouter(prefix="/ask")

LIMIT = 5

def create_query_embedding(query):
    print('query start for jina', query)
    try:
        response = requests.post(
            "https://api.jina.ai/v1/embeddings",
            headers={
                "Authorization": f"Bearer {JINA_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=(5, 30),  # Connection timeout and socket read timeout, in seconds.
            json={
                "model": "jina-embeddings-v5-text-small",
                "task": "retrieval.query",
                "dimensions": 1024,
                "input": [query],
            },
        )
        response.raise_for_status()
    except requests.exceptions.Timeout as exc:
        raise HTTPException(
            status_code=504,
            detail="Jina embedding request timed out. Please try again.",
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail="Jina embedding request failed.",
        ) from exc

    body = response.json()
    print('body', body)
    return body["data"][0]["embedding"]



@router.post('/')
def ask_question(body: AskPostRequest, db: Session = Depends(get_db)):
    query_embedding = create_query_embedding(body.query)
    print('query_embedding', query_embedding)
    results = db.query(DocumentChunks).order_by(
        DocumentChunks.embeddings.cosine_distance(query_embedding)
    ).limit(LIMIT).all()
    context = build_context(results)
    answer = generate_answer(body.query, context)
    return {
        "answer": answer,
        "sources": [
            {
                "source_id": f"SOURCE_{idx}",
                "page_num": chunk.page_num,
                "chapter": chunk.chapter,
                "section": chunk.section,
                "content": chunk.content,
                "document_key": chunk.document_key
            } 
            for idx, chunk in enumerate(results, start=1)
        ]

    }


@router.get("/get-retrieval-url")
def get_retrieval_url(document_name: str = Query(...)):
    if "/" in document_name or ".." in document_name:
        raise HTTPException(status_code=400, detail="Invalid document name")

    base_url = f"{cloudfront_base_url}/pages/{document_name}"

    policy, expires_at = create_policy(
        f"{base_url}/*",
        cloudfront_url_expiration,
    )
    print('cloudfront_private_key', cloudfront_private_key)
    signature = sign_policy(
        policy,
        cloudfront_private_key,
    )

    signed_query = (
        f"Policy={cloudfront_base64(policy)}"
        f"&Signature={signature}"
        f"&Key-Pair-Id={cloudfront_key_pair_id}"
    )

    return {
        "baseUrl": base_url,
        "signedQuery": signed_query,
        "expiresAt": expires_at,
    }
