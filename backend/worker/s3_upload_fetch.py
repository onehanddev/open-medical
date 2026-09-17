import json
from urllib.parse import unquote_plus
import time
import boto3
import logging
from botocore.exceptions import ClientError
from collections import defaultdict
from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import DocumentStream
import pymupdf
import pymupdf4llm
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
import io
import os
from pprint import pformat
# import voyageai
from dotenv import load_dotenv
# from sklearn.metrics.pairwise import cosine_similarity
import requests
from db import SessionLocal
from models import DocumentChunks
from config.get_env import cloudflare_acccount_id, cloudflare_api_token
from concurrent.futures import ThreadPoolExecutor
from itertools import repeat
import os
import psutil
import threading
import gc

print("========== BUILD: SLIM-LOG-V1 ==========", flush=True)

process = psutil.Process(os.getpid())

def log_memory(label):
    mb = process.memory_info().rss / 1024 / 1024
    print(f"[MEMORY] {label}: {mb:.0f} MB")

def monitor_memory():
    while True:
        memory_mb = process.memory_info().rss / 1024 / 1024
        print(f"[MEMORY MONITOR] {memory_mb:.0f} MB", flush=True)
        time.sleep(15)

# initialize voyage ai to make embeddings
# vo = voyageai.Client()

#heading based text splitter
heading_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[
        ('#', 'chapter'),
        ('##', 'section'),
        ('###', 'subsection'),
    ]
)


#token based text splitter
token_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    encoding_name='cl100k_base',
    chunk_size=500,
    chunk_overlap=50
)

logging.basicConfig(level=logging.INFO)

s3 = boto3.client('s3')
options = PdfPipelineOptions(
    do_ocr=False,
    do_picture_classification=False,
    do_table_structure=False,  # Disable if table structure isn't needed.
)
converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=options)
    }
)

def read_s3_object(bucket_name, file_key):
    """Read an S3 object, or skip a stale event for an object that is gone."""
    try:
        response = s3.get_object(Bucket=bucket_name, Key=file_key)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in {"NoSuchKey", "404", "NotFound"}:
            logging.warning(
                "Skipping stale S3 event because the object no longer exists: "
                "s3://%s/%s",
                bucket_name,
                file_key,
            )
            return None
        raise

    return response["Body"].read()

def insert_chunk_to_db(chunks, embeddings, document_key):

    rows = []

    if len(chunks) != len(embeddings):
        raise ValueError(
        f"Chunks/embeddings mismatch: "
        f"{len(chunks)} chunks, {len(embeddings)} embeddings"

    )

    for idx, chunk in enumerate(chunks):
        new_chunk = DocumentChunks(
                    document_key=document_key,
                    page_num=chunk.metadata.get("page_num"),
                    chapter=chunk.metadata.get("chapter"),
                    section=chunk.metadata.get("section"),
                    subsection=chunk.metadata.get("subsection"),
                    metadata_=chunk.metadata,
                    chunk_index=chunk.metadata.get("chunk_index"),
                    content=chunk.page_content,
                    embeddings=embeddings[idx]
        )
        rows.append(new_chunk)


    with SessionLocal() as db:
        try:
            db.add_all(rows)
            db.commit()
            logging.info(
                    "Inserted %s chunks for document %s",
                    len(rows),
                    document_key,
                )
        except Exception:
            db.rollback()
            raise


def cloudflare_embed(inputs):
    response = requests.post(
        f"https://api.cloudflare.com/client/v4/accounts/{cloudflare_acccount_id}/ai/run/@cf/baai/bge-m3",
        headers={"Authorization": f"Bearer {cloudflare_api_token}"},
        json={"text": inputs},
        timeout=(5, 30),
    )

    response.raise_for_status()

    body = response.json()

    if not body.get("success"):
        raise ValueError("Cloudflare embedding request failed.")
    embeddings = body["result"]["data"]
    if len(embeddings) != len(inputs):
        raise ValueError("Cloudflare embedding count does not match input count.")
    return embeddings


def create_embeddings(chunks):

    BATCH_SIZE = 100

    all_embeddings = []

    for start in range(0, len(chunks), BATCH_SIZE):
        to_embed_chunks = chunks[start:start+BATCH_SIZE]
        doc_embeddings = cloudflare_embed(
            [chunk.page_content for chunk in to_embed_chunks]
        )
        all_embeddings.extend(doc_embeddings)
        print(

            f"Embedded {min(start + BATCH_SIZE, len(chunks))}/{len(chunks)} chunks"

        )
        time.sleep(40)

    return all_embeddings





def get_pages_with_tables(doc):
    pages_with_tables = defaultdict(bool)

    for table in doc.tables:
        if table.prov and len(table.prov) > 0:
            page_num = table.prov[0].page_no
            pages_with_tables[page_num] = True

    return pages_with_tables


def get_pages_with_visuals(doc):
     # A detected picture exists even if its type cannot be classified.
    pages_with_visuals = defaultdict(lambda: {
        "picture": False,
        "diagram": False,
        "chart": False
    })

    for picture in doc.pictures:
        classification = getattr(getattr(picture, "meta", None), "classification", None)
        predictions = list(getattr(classification, "predictions", None) or [])
        if not predictions:
            # Support documents produced with the older annotation schema.
            for annotation in getattr(picture, "annotations", []) or []:
                predictions.extend(getattr(annotation, "predicted_classes", []) or [])

        # Alternative predictions are not additional picture types.
        best = max(predictions, key=lambda prediction: prediction.confidence, default=None)
        label = best.class_name.lower() if best else ""
        is_diagram = any(kind in label for kind in ("diagram", "flowchart", "flow_chart"))
        is_chart = not is_diagram and any(kind in label for kind in ("chart", "graph", "plot"))
        for provenance in picture.prov or []:
            page_num = provenance.page_no
            pages_with_visuals[page_num]["picture"] = True
            pages_with_visuals[page_num]["diagram"] |= is_diagram
            pages_with_visuals[page_num]["chart"] |= is_chart

    return pages_with_visuals

    
def get_parser_to_use(is_rich):
    return 'docling' if is_rich else 'pymupdf4llm'

def parse_bytes_with_parser(parser_name, page_num, doc, pdf):
    if parser_name == 'docling':
        print(f'page {page_num} parsed by docling')
        return doc.export_to_markdown(page_no=page_num)
    elif parser_name == 'pymupdf4llm':
        print(f'page {page_num} parsed by pymupdf4llm')
        return pymupdf4llm.to_markdown(
            pdf,
            pages=[page_num - 1],  # PyMuPDF uses zero-based indexes
        )


    raise ValueError(f"Unknown parser: {parser_name}")

def chunk_markdown_content(page_contents):

    chunks = []

    for page in page_contents:
        sections = heading_splitter.split_text(page["markdown"])

        for section in sections:
            section.metadata["page_num"] = page["page_num"]

        chunks.extend(
            token_splitter.split_documents(sections)
        )

    for idx, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = idx

    return chunks

def upload_page(page_content, bucket_name, page_key):
    key = f"{page_key}{page_content["page_num"]}.md"
    s3.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=page_content["markdown"].encode("utf-8"),
            ContentType="text/markdown; charset=utf-8",
        )
    return key


def save_md_to_s3(page_contents, bucket_name, file_key):

    WORKERS_PER_RUN = 10

    source_name = file_key.removeprefix("pdf/").rsplit(".", 1)[0]
    page_key = f"pages/{source_name}/page_"

    with ThreadPoolExecutor(max_workers=WORKERS_PER_RUN) as executor:
        uploaded_keys = list(executor.map(upload_page, page_contents, repeat(bucket_name), repeat(page_key)))

    

    logging.info(
        "uploaded_keys:",
        bucket_name,
        uploaded_keys,
    )

    return uploaded_keys


def parse_bytes(file_bytes, bucket_name, file_key):
    source = DocumentStream(name=file_key, stream=io.BytesIO(file_bytes))

    threading.Thread(
        target=monitor_memory,
        daemon=True,
    ).start()

    log_memory("BEFORE DOCLING CONVERT")
    # DOCLING
    result = converter.convert(source)

    log_memory("AFTER DOCLING CONVERT")

    doc = result.document

    pages_with_tables = get_pages_with_tables(doc)
    pages_with_visuals = get_pages_with_visuals(doc)

    page_contents = []

    with pymupdf.open(stream=file_bytes, filetype="pdf") as pdf:
        for page_num in sorted(doc.pages):
            if page_num % 25 == 0:
                log_memory(f"AFTER PAGE {page_num}")
            has_table = pages_with_tables.get(page_num, False)
            visual_flags = pages_with_visuals.get(page_num, {})
            has_picture = visual_flags.get("picture", False)

            parser_name = get_parser_to_use(has_table or has_picture)

            markdown = parse_bytes_with_parser(parser_name, page_num, doc, pdf)
            page_contents.append({
                "page_num": page_num,
                "markdown": markdown
            })

    markdown_content = "\n\n".join(
        page["markdown"] for page in page_contents
    )
    log_memory("AFTER PDF PARSING")
    #start chunking with splitter
    chunks = chunk_markdown_content(page_contents=page_contents)
    log_memory("AFTER CHUNKING")
    embeddings = create_embeddings(chunks)
    log_memory("AFTER EMBEDDINGS")
    insert_chunk_to_db(
        chunks,
        embeddings,
        document_key = file_key
    )
    log_memory("AFTER DATABASE SAVE")

    save_md_to_s3(page_contents=page_contents, bucket_name=bucket_name, file_key=file_key)

    return markdown_content


def lambda_handler(event, context):
        log_memory("START")
        for message in event.get("Records", []):
            body = json.loads(message['Body'])

            for record in body.get('Records', []):

                print("SQS BODY:", record.get("Body"))
                bucket_name = record["s3"]["bucket"]["name"]
                file_key = unquote_plus(record["s3"]["object"]["key"])
                print("SQS FILE NAME:", file_key)


                event_name = record.get("eventName", "")

                if not event_name.startswith("ObjectCreated:"):
                    logging.info(
                        "Skipping non-create S3 event: event=%s key=%s",
                        event_name,
                        file_key,
                    )
                    continue

                if not file_key.startswith("pdf/") or not file_key.lower().endswith(".pdf"):
                    logging.info("Skipping non-PDF upload event: %s", file_key)
                    continue

                logging.info(
                    "S3 event=%r bucket=%r raw_key=%r decoded_key=%r",
                    record.get("eventName"),
                    bucket_name,
                    record["s3"]["object"]["key"],
                    file_key,
                )

                file_bytes = read_s3_object(bucket_name, file_key)
                log_memory("AFTER S3 DOWNLOAD")
                if file_bytes is None:
                    continue

                parse_bytes(file_bytes, bucket_name, file_key)


def poll_sqs_forever(queue_url, wait_seconds=20):
    """EKS entrypoint: long-poll SQS and feed messages to lambda_handler."""
    sqs = boto3.client("sqs")
    logging.info("Polling SQS queue: %s", queue_url)
    while True:
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=wait_seconds,
        )
        messages = response.get("Messages", [])
        if not messages:
            continue
        lambda_handler({"Records": messages}, None)
        for message in messages:
            try:
                sqs.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=message["ReceiptHandle"],
                )
            finally:
                message = None
                response = None

                 # Ask Python to collect unreachable objects
                gc.collect()

                log_memory("AFTER CLEANUP")




if __name__ == "__main__":
    from config.get_env import sqs_queue_url as _queue_url

    if not _queue_url:
        raise RuntimeError(
            "SQS_QUEUE_URL is missing. Set it in the environment."
        )
    poll_sqs_forever(_queue_url)



           
