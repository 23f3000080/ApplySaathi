# b2_service.py

import boto3
from flask import current_app
from botocore.client import Config


def get_b2_client():
    """
    Create and return a B2 S3-compatible client
    using Signature Version 4 (required for Backblaze B2).
    """
    return boto3.client(
        service_name="s3",
        endpoint_url=current_app.config["B2_ENDPOINT"],
        aws_access_key_id=current_app.config["B2_ACCESS_KEY"],
        aws_secret_access_key=current_app.config["B2_SECRET_KEY"],
        config=Config(signature_version="s3v4")  # 🔥 IMPORTANT FIX
    )


def upload_file_to_b2(file, filename):
    """
    Upload file object to B2 bucket.
    `filename` must be the object key (e.g. user_1/form_25/file.jpg)
    """
    client = get_b2_client()

    client.upload_fileobj(
        file,
        current_app.config["B2_BUCKET_NAME"],
        filename,
        ExtraArgs={
            "ContentType": file.content_type
        }
    )


def generate_signed_url(file_key, expiry=600):
    """
    Generate a temporary signed URL for private file access.
    Default expiry = 10 minutes (600 seconds).
    """
    client = get_b2_client()

    return client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": current_app.config["B2_BUCKET_NAME"],
            "Key": file_key,
        },
        ExpiresIn=expiry,
    )


def delete_file_from_b2(file_key):
    """
    Delete file from B2 bucket.
    """
    client = get_b2_client()

    client.delete_object(
        Bucket=current_app.config["B2_BUCKET_NAME"],
        Key=file_key
    )