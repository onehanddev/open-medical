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
from config.db import SessionLocal
from models import DocumentChunks
from config.get_env import jina_api_key as JINA_API_KEY
from concurrent.futures import ThreadPoolExecutor
from itertools import repeat

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

# Create SQS client
sqs = boto3.client('sqs')
s3 = boto3.client('s3')
options = PdfPipelineOptions(
    do_ocr=False,
    do_picture_classification=True,
    do_table_structure=True,  # Disable if table structure isn't needed.
)
converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=options)
    }
)

queue_url = 'pdf-uploaded-queue'

EMBED_QUERY = "which is more potent to capillary LT or histamine?"


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


def jina_embed(type, input):
    if type == "doc":
        inputs = [chunk.page_content for chunk in input]
    else:
        inputs = [input]

    response = requests.post(
        "https://api.jina.ai/v1/embeddings",
        headers={
            "Authorization": f"Bearer {JINA_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "jina-embeddings-v5-text-small",
            "task": "retrieval.passage" if type == "doc" else "retrieval.query",
            "dimensions": 1024,
            "input": inputs,
        },
    )

    response.raise_for_status()

    body = response.json()

    if type == "doc":
        return [
            item["embedding"]
            for item in body["data"]
        ]

    return body["data"][0]["embedding"]


def create_embeddings(chunks):

    BATCH_SIZE = 100

    all_embeddings = []

    for start in range(0, len(chunks), BATCH_SIZE):
        to_embed_chunks = chunks[start:start+BATCH_SIZE]
        doc_embeddings = jina_embed(
            "doc",
            to_embed_chunks
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

    # DOCLING
    result = converter.convert(source)

    doc = result.document

    pages_with_tables = get_pages_with_tables(doc)
    pages_with_visuals = get_pages_with_visuals(doc)

    page_contents = []

    with pymupdf.open(stream=file_bytes, filetype="pdf") as pdf:
        for page_num in sorted(doc.pages):
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

    #start chunking with splitter
    chunks = chunk_markdown_content(page_contents=page_contents)
    embeddings = create_embeddings(chunks)

    insert_chunk_to_db(
        chunks,
        embeddings,
        document_key = file_key
    )

    save_md_to_s3(page_contents=page_contents, bucket_name=bucket_name, file_key=file_key)

    # os.makedirs("./downloads", exist_ok=True)
    
    # output_path = "./downloads/downloaded_document.md"

    # with open(output_path, "w", encoding="utf-8") as file:
    #     file.write(markdown_content)

    return markdown_content



# CORE FILE CODE TO LISTEN/POLL TO SQS


while True:

    # Long poll for message on provided SQS queue
    response = sqs.receive_message(
        QueueUrl=queue_url,
        AttributeNames=[
            'SentTimestamp'
        ],
        MaxNumberOfMessages=1,
        MessageAttributeNames=[
            'All'
        ],
        WaitTimeSeconds=20
    )

    messages = response.get('Messages', [])
    if not messages:
        print("No messages found. Polling again..")
        continue

    for message in messages:
        body = json.loads(message['Body'])
        reciept_handle = message['ReceiptHandle']

        for record in body.get('Records', []):
            bucket_name = record["s3"]["bucket"]["name"]
            file_key = unquote_plus(record["s3"]["object"]["key"])

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
            if file_bytes is None:
                continue

            pdf_text = parse_bytes(file_bytes, bucket_name, file_key)



        sqs.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=reciept_handle
        )

        print('Message deleted from sqs')
