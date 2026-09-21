import boto3
import json
import os
from urllib.parse import unquote_plus

ecs = boto3.client("ecs")


def _load_sqs_body(record):
    """Parse an SQS record body, unwrapping an SNS envelope if present."""
    body = json.loads(record["body"])
    # S3 -> SNS -> SQS wraps the S3 event JSON in a "Message" string.
    if isinstance(body, dict) and "Message" in body:
        body = json.loads(body["Message"])
    return body


def _launch_worker(bucket_name, file_key):
    response = ecs.run_task(
        cluster=os.environ["ECS_CLUSTER"],
        taskDefinition=os.environ["ECS_TASK_DEFINITION"],
        launchType="FARGATE",
        count=1,
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": [os.environ["SUBNET_ID"]],
                "securityGroups": [os.environ["SECURITY_GROUP_ID"]],
                "assignPublicIp": "ENABLED",
            }
        },
        overrides={
            "containerOverrides": [
                {
                    "name": os.environ["CONTAINER_NAME"],
                    "environment": [
                        {"name": "PDF_BUCKET", "value": bucket_name},
                        {"name": "PDF_KEY", "value": file_key},
                    ],
                }
            ]
        },
    )
    failures = response.get("failures", [])
    if failures:
        raise RuntimeError(f"ECS run_task failures: {failures}")
    return response


def lambda_handler(event, context):
    print("lambda handler started")
    batch_item_failures = []

    for record in event.get("Records", []):
        message_id = record.get("messageId")
        try:
            print(f"SQS messageId={message_id} body={record.get('body')}")
            body = _load_sqs_body(record)
            s3_records = body.get("Records", [])
            if not s3_records:
                print(f"No S3 Records in SQS message {message_id}, skipping")
                continue

            for s3_record in s3_records:
                event_name = s3_record.get("eventName", "")
                bucket_name = s3_record["s3"]["bucket"]["name"]
                raw_key = s3_record["s3"]["object"]["key"]
                file_key = unquote_plus(raw_key)

                if not event_name.startswith("ObjectCreated:"):
                    print(
                        f"Skipping non-create S3 event: event={event_name} key={file_key}"
                    )
                    continue

                if not file_key.startswith("pdf/") or not file_key.lower().endswith(
                    ".pdf"
                ):
                    print(f"Skipping non-PDF upload event: {file_key}")
                    continue

                print(
                    f"S3 event={event_name!r} bucket={bucket_name!r} "
                    f"raw_key={raw_key!r} decoded_key={file_key!r}"
                )
                print(f"Starting worker for s3://{bucket_name}/{file_key}")

                response = _launch_worker(bucket_name, file_key)
                print(response)
        except Exception as exc:
            print(f"Failed to process SQS message {message_id}: {exc}")
            # Report per-message so only failed messages are retried.
            if message_id:
                batch_item_failures.append({"itemIdentifier": message_id})
            else:
                raise

    return {"batchItemFailures": batch_item_failures}
