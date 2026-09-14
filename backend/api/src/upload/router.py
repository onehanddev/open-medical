from fastapi import APIRouter, Query
from uuid import uuid4
import boto3
import logging
from botocore.config import Config
from boto3.exceptions import S3UploadFailedError
from backend.api.config.get_env import aws_bucket_name, aws_expiry, aws_region_name

router = APIRouter(prefix="/upload")


def create_presigned_url(
    bucket_name, object_name, region_name, expiration=3600
):
    """Generate a presigned URL to upload an S3 object.

    :param bucket_name: string
    :param object_name: string
    :param region_name: string
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """

    # Generate a presigned URL for the S3 object
    s3_client = boto3.client(
        's3',
        region_name=region_name,
        config=Config(
            signature_version='s3v4',
            s3={'addressing_style': 'virtual'},
        ),
    )
    try:
        response = s3_client.generate_presigned_url(
            'put_object',
            Params={'Bucket': bucket_name, 'Key': object_name},
            ExpiresIn=expiration,
        )
    except S3UploadFailedError as e:
        logging.error(e)
        return None

    # The response contains the presigned URL
    return response

@router.get('/presigned-url')
def get_presigned_url(file_name: str = Query(..., min_length=1, max_length=255)):
    object_name = f"pdf/{file_name}"
    return create_presigned_url(aws_bucket_name, object_name, aws_region_name, aws_expiry)
