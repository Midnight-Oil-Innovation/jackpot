import os

import boto3
from botocore.client import Config as BotoConfig

from backend.config import get_settings

settings = get_settings()


def _get_client():
    if settings.storage_endpoint:
        return boto3.client(
            "s3",
            endpoint_url=settings.storage_endpoint,
            aws_access_key_id=settings.storage_access_key,
            aws_secret_access_key=settings.storage_secret_key,
            config=BotoConfig(signature_version="s3v4"),
            region_name="us-east-1",
        )
    return boto3.client(
        "s3",
        endpoint_url="https://storage.googleapis.com",
        aws_access_key_id=os.environ.get("GCS_HMAC_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("GCS_HMAC_SECRET"),
        config=BotoConfig(signature_version="s3v4"),
        region_name="auto",
    )


def upload_fileobj(fileobj, bucket: str, key: str) -> str:
    _get_client().upload_fileobj(fileobj, bucket, key)
    return f"{'s3' if settings.storage_endpoint else 'gs'}://{bucket}/{key}"


def generate_presigned_url(bucket: str, key: str, expires: int = 3600) -> str:
    return _get_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )


def generate_presigned_upload_url(bucket: str, key: str, expires: int = 86400) -> str:
    return _get_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )


def object_exists(bucket: str, key: str) -> bool:
    try:
        _get_client().head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False
