from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from urllib.parse import quote
from config.db import get_db
from config.get_env import (
    cloudfront_base_url,
    cloudfront_key_pair_id,
    cloudfront_private_key,
    cloudfront_url_expiration,
    cloudflare_acccount_id,
    cloudflare_api_token
)
import requests
from models import DocumentChunks
from schema.ask import AskPostRequest
from utils.llm import build_context, generate_answer
from utils.cloudfront_signer import create_policy, sign_policy, cloudfront_base64
from opentelemetry import trace
from fastapi.responses import StreamingResponse
import json

tracer = trace.get_tracer(__name__)

router = APIRouter(prefix="/ask")

LIMIT = 5

def create_query_embedding(query):
    with tracer.start_as_current_span('embeddings.query') as span:
        span.set_attribute('query', query)
        span.set_attribute('model', 'cloudflare_bge-m3')
        try:
            response = requests.post(
                f"https://api.cloudflare.com/client/v4/accounts/{cloudflare_acccount_id}/ai/run/@cf/baai/bge-m3",
                headers={"Authorization": f"Bearer {cloudflare_api_token}"},
                json={"text": [query]},
                timeout=(5, 30),
            )
            response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise HTTPException(
                status_code=504,
                detail="Cloudflare embedding request timed out. Please try again.",
            ) from exc
        except requests.exceptions.RequestException as exc:
            error_response = exc.response
            print(
                "[DEBUG-cloudflare] Embedding request failed:",
                f"exception={type(exc).__name__}",
                f"message={exc}",
                f"status={error_response.status_code if error_response is not None else None}",
                f"body={error_response.text if error_response is not None else None}",
                flush=True,
            )
            raise HTTPException(
                status_code=502,
                detail="Cloudflare embedding request failed.",
            ) from exc

        body = response.json()
        if not body.get("success"):
            raise HTTPException(
                status_code=502,
                detail="Cloudflare embedding request failed.",
            )
        return body["result"]["data"][0]


def build_retrieval_query(query, history):

    RECENT_MSG_COUNT = 2

    user_messages = [
        msg.content for msg in history if msg.role == 'user'
    ]

    l = len(user_messages)

    recent_user_message = history[l-RECENT_MSG_COUNT:l]

    return f"""
       {f"previous questions: {"\n".join(recent_user_message)}" if l > 0 else ""}
        current question: {query}
    """



@router.post('/')
def ask_question(body: AskPostRequest, db: Session = Depends(get_db)):
    query = build_retrieval_query(body.query, body.history)
    query_embedding = create_query_embedding(query)
    results = db.query(DocumentChunks).order_by(
        DocumentChunks.embeddings.cosine_distance(query_embedding)
    ).limit(LIMIT).all()
    context = build_context(results)

    async def event_stream():
        async for token in generate_answer(body.query, body.history, context):
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        print(f"data: {json.dumps({'type': 'token', 'content': token})}\n\n")

        yield f"data: {json.dumps({
            "type": "sources",
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

        })}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


    


@router.get("/get-retrieval-url")
def get_retrieval_url(document_name: str = Query(...)):
    if "/" in document_name or ".." in document_name:
        raise HTTPException(status_code=400, detail="Invalid document name")

    encoded_document_name = quote(document_name, safe="")
    base_url = f"{cloudfront_base_url.rstrip('/')}/pages/{encoded_document_name}"

    policy, expires_at = create_policy(
        f"{base_url}/*",
        cloudfront_url_expiration,
    )
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
