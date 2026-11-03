import asyncio
import hashlib
import io
from dataclasses import dataclass

import boto3
from botocore.config import Config
from PIL import Image, ImageOps, UnidentifiedImageError

from .config import get_settings
from .errors import APIError


ALLOWED_IMAGE_TYPES = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
IMAGE_FORMAT_CONTENT_TYPES = {
    "JPEG": "image/jpeg",
    "MPO": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


@dataclass
class VerifiedImage:
    byte_size: int
    content_type: str
    width: int
    height: int
    checksum: str


@dataclass
class VerifiedPdf:
    byte_size: int
    checksum: str
    page_count: int
    data: bytes


class PrivateObjectStorage:
    def __init__(self):
        self.settings = get_settings()
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.settings.s3_endpoint_url,
                region_name=self.settings.s3_region,
                aws_access_key_id=self.settings.s3_access_key_id,
                aws_secret_access_key=self.settings.s3_secret_access_key,
                config=Config(signature_version="s3v4"),
            )
        return self._client

    def require_configured(self) -> None:
        if not self.settings.s3_access_key_id or not self.settings.s3_secret_access_key or not self.settings.s3_bucket:
            raise APIError(503, "storage_not_configured", "Private object storage is not configured")

    def create_upload_put(self, object_key: str, content_type: str) -> str:
        self.require_configured()
        return self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.settings.s3_bucket,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=self.settings.s3_signed_url_seconds,
        )

    def create_read_url(self, object_key: str) -> str:
        self.require_configured()
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.settings.s3_bucket, "Key": object_key},
            ExpiresIn=self.settings.s3_signed_url_seconds,
        )

    def verify_uploaded_image(self, object_key: str, expected_type: str) -> VerifiedImage:
        self.require_configured()
        response = self.client.get_object(Bucket=self.settings.s3_bucket, Key=object_key)
        data = response["Body"].read(self.settings.image_max_bytes + 1)
        if len(data) > self.settings.image_max_bytes:
            raise APIError(422, "image_too_large", "Uploaded image exceeds the configured size limit")
        try:
            with Image.open(io.BytesIO(data)) as image:
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > self.settings.image_max_pixels:
                    raise APIError(422, "image_dimensions_too_large", "Uploaded image exceeds the configured pixel limit")
                image.verify()
            with Image.open(io.BytesIO(data)) as source:
                width, height = source.size
                if width <= 0 or height <= 0 or width * height > self.settings.image_max_pixels:
                    raise APIError(422, "image_dimensions_too_large", "Uploaded image exceeds the configured pixel limit")
                actual_format = source.format
                image = ImageOps.exif_transpose(source)
                image.load()
                width, height = image.size
        except APIError:
            raise
        except (Image.DecompressionBombError, UnidentifiedImageError, OSError):
            raise APIError(422, "invalid_image", "Uploaded file is not a readable image")
        expected_format = ALLOWED_IMAGE_TYPES.get(expected_type)
        if not expected_format or IMAGE_FORMAT_CONTENT_TYPES.get(actual_format) != expected_type:
            raise APIError(422, "image_type_mismatch", "Uploaded image content does not match its declared type")
        image.thumbnail(
            (self.settings.image_max_dimension, self.settings.image_max_dimension),
            Image.Resampling.LANCZOS,
        )
        if expected_format == "JPEG" and image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        output = io.BytesIO()
        save_options = {"optimize": True}
        if expected_format in {"JPEG", "WEBP"}:
            save_options["quality"] = self.settings.image_quality
        image.save(output, format=expected_format, **save_options)
        normalized = output.getvalue()
        if len(normalized) > self.settings.image_max_bytes:
            raise APIError(422, "image_too_large", "Normalized image exceeds the configured size limit")
        self.client.put_object(
            Bucket=self.settings.s3_bucket,
            Key=object_key,
            Body=normalized,
            ContentType=expected_type,
        )
        width, height = image.size
        return VerifiedImage(len(normalized), expected_type, width, height, hashlib.sha256(normalized).hexdigest())

    def delete(self, object_key: str) -> None:
        self.require_configured()
        self.client.delete_object(Bucket=self.settings.s3_bucket, Key=object_key)

    def verify_uploaded_pdf(self, object_key: str) -> VerifiedPdf:
        self.require_configured()
        response = self.client.get_object(Bucket=self.settings.s3_bucket, Key=object_key)
        data = response["Body"].read(self.settings.textbook_max_bytes + 1)
        if len(data) > self.settings.textbook_max_bytes:
            raise APIError(422, "textbook_too_large", "Uploaded textbook exceeds the configured size limit")
        if not data.startswith(b"%PDF-"):
            raise APIError(422, "invalid_textbook_pdf", "Uploaded textbook is not a PDF")
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            page_count = len(reader.pages)
        except Exception as exc:
            raise APIError(422, "invalid_textbook_pdf", "Uploaded textbook PDF is unreadable") from exc
        if page_count < 1:
            raise APIError(422, "invalid_textbook_pdf", "Uploaded textbook PDF contains no pages")
        return VerifiedPdf(len(data), hashlib.sha256(data).hexdigest(), page_count, data)


storage = PrivateObjectStorage()


async def run_storage(function, *args):
    return await asyncio.to_thread(function, *args)
