import os

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from backend.config import get_settings


class StorageError(Exception):
    """Raised when a storage operation fails with a meaningful message."""

    pass


def _get_client():
    settings = get_settings()
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


def stage_file(fileobj, destination_key: str) -> str:
    """Upload a file to the staging bucket. Returns the URI."""
    settings = get_settings()
    bucket = settings.storage_bucket_staging
    try:
        _get_client().upload_fileobj(fileobj, bucket, destination_key)
    except ClientError as e:
        raise StorageError(
            f"Failed to stage file '{destination_key}' to bucket '{bucket}': "
            f"{e.response['Error']['Message']}"
        ) from e
    prefix = "s3" if settings.storage_endpoint else "gs"
    return f"{prefix}://{bucket}/{destination_key}"


def move_to_sequences(staging_key: str, sequences_key: str) -> str:
    """Move a scrubbed file from staging to the sequences bucket."""
    settings = get_settings()
    client = _get_client()
    src_bucket = settings.storage_bucket_staging
    dst_bucket = settings.storage_bucket_sequences
    try:
        client.copy_object(
            CopySource={"Bucket": src_bucket, "Key": staging_key},
            Bucket=dst_bucket,
            Key=sequences_key,
        )
        client.delete_object(Bucket=src_bucket, Key=staging_key)
    except ClientError as e:
        raise StorageError(
            f"Failed to move '{staging_key}' to sequences: " f"{e.response['Error']['Message']}"
        ) from e
    prefix = "s3" if settings.storage_endpoint else "gs"
    return f"{prefix}://{dst_bucket}/{sequences_key}"


def generate_presigned_url(bucket: str, key: str, ttl_seconds: int = 3600) -> str:
    """Generate a presigned download URL."""
    try:
        return _get_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=ttl_seconds,
        )
    except ClientError as e:
        raise StorageError(
            f"Failed to generate presigned URL for '{key}': " f"{e.response['Error']['Message']}"
        ) from e


def generate_signed_upload_url(bucket: str, key: str, ttl_seconds: int = 14400) -> str:
    """Generate a signed upload URL (4-hour default TTL)."""
    try:
        return _get_client().generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=ttl_seconds,
        )
    except ClientError as e:
        raise StorageError(
            f"Failed to generate signed upload URL for '{key}': "
            f"{e.response['Error']['Message']}"
        ) from e


def delete_file(bucket: str, key: str) -> None:
    """Delete a file from a bucket."""
    try:
        _get_client().delete_object(Bucket=bucket, Key=key)
    except ClientError as e:
        raise StorageError(
            f"Failed to delete '{key}' from bucket '{bucket}': " f"{e.response['Error']['Message']}"
        ) from e


def file_exists(bucket: str, key: str) -> bool:
    """Check if a file exists without downloading it."""
    try:
        _get_client().head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise
