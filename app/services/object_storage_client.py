"""S3-compatible object storage for FIT files."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast


import boto3
from botocore.exceptions import ClientError

from app.config import settings
from app.core.logging_utils import log_event


class ObjectStorageError(Exception):
    """Base class for object-storage failures."""


class ObjectStorageUploadError(ObjectStorageError):
    """PUT call failed (network / 5xx / IO error)."""


class ObjectStorageConflictError(ObjectStorageError):
    """Key already exists. Raw FIT files are immutable."""


class ObjectStorageNotConfiguredError(ObjectStorageError):
    """Object storage not configured (503)."""


@dataclass(frozen=True)
class StoredFitObject:
    """Returned by ObjectStorageClient.upload_fit."""

    key: str
    byte_count: int
    content_md5: str


@dataclass(frozen=True)
class StoredCleanedStream:
    """Returned by ObjectStorageClient.upload_cleaned_stream."""

    key: str
    byte_count: int
    content_md5: str


class ObjectStorageClient:
    """S3-compatible object storage client."""

    LOCAL_FALLBACK_ROOT = Path("./var/object-storage")

    def __init__(
        self,
        *,
        endpoint_url: str | None = None,
        bucket: str | None = None,
        region: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        use_ssl: bool | None = None,
    ) -> None:
        self._endpoint_url = (
            endpoint_url if endpoint_url is not None else settings.S3_ENDPOINT_URL
        )
        self._bucket = bucket or settings.S3_BUCKET
        self._region = region or settings.S3_REGION
        self._access_key = access_key or settings.S3_ACCESS_KEY
        self._secret_key = secret_key or settings.S3_SECRET_KEY
        self._use_ssl = use_ssl if use_ssl is not None else settings.S3_USE_SSL
        self._use_local_fallback = (
            not self._endpoint_url and not self._access_key and not self._secret_key
        )
        self._s3_client: Any = None
        if not self._use_local_fallback:
            self._s3_client = cast(
                Any,
                boto3.client(  # type: ignore[reportUnknownMemberType]
                    "s3",
                    endpoint_url=self._endpoint_url or None,
                    region_name=self._region,
                    aws_access_key_id=self._access_key or None,
                    aws_secret_access_key=self._secret_key or None,
                    use_ssl=self._use_ssl,
                ),
            )

    @staticmethod
    def build_fit_key(
        athlete_id: uuid.UUID, activity_date: date, suffix_uuid: uuid.UUID
    ) -> str:
        """Build canonical object key for a FIT file."""
        return f"fit-files/{athlete_id}/{activity_date.isoformat()}/{suffix_uuid}.fit"

    @staticmethod
    def build_cleaned_stream_key(athlete_id: uuid.UUID, activity_id: uuid.UUID) -> str:
        """Build deterministic object key for a cleaned sensor stream."""
        return f"cleaned-streams/{athlete_id}/{activity_id}/stream.gz"

    async def upload_fit(
        self,
        *,
        athlete_id: uuid.UUID,
        activity_date: date,
        file_bytes: bytes,
        content_type: str = "application/octet-stream",
        suffix_uuid: uuid.UUID | None = None,
    ) -> StoredFitObject:
        """Upload a FIT file to object storage."""
        suffix = suffix_uuid or uuid.uuid4()
        key = self.build_fit_key(athlete_id, activity_date, suffix)
        loop = asyncio.get_running_loop()

        if self._use_local_fallback:
            return await loop.run_in_executor(None, self._upload_local, key, file_bytes)

        try:
            await loop.run_in_executor(
                None,
                lambda: self._s3_client.put_object(  # type: ignore[union-attr]
                    Bucket=self._bucket,
                    Key=key,
                    Body=file_bytes,
                    ContentType=content_type,
                    Metadata={
                        "athlete_id": str(athlete_id),
                        "activity_date": activity_date.isoformat(),
                    },
                ),
            )
        except ClientError as exc:
            code: str = (
                cast(dict[str, Any], exc.response).get("Error", {}).get("Code", "")
            )
            if code in {"PreconditionFailed", "x-amz-precondition-failed"}:
                log_event(
                    event="object_storage.upload.conflict",
                    athlete_id=str(athlete_id),
                    outcome="failed",
                )
                raise ObjectStorageConflictError(
                    f"object already exists at {key}"
                ) from exc
            log_event(
                event="object_storage.upload.failed",
                athlete_id=str(athlete_id),
                outcome="failed",
            )
            raise ObjectStorageUploadError(
                f"s3 put_object failed for {key}: {exc}"
            ) from exc

        log_event(
            event="object_storage.upload.success",
            athlete_id=str(athlete_id),
            outcome="success",
        )
        return StoredFitObject(
            key=key,
            byte_count=len(file_bytes),
            content_md5=md5_base64(file_bytes),
        )

    async def download_fit(self, key: str) -> bytes:
        """Download a previously-stored FIT file as raw bytes."""
        loop = asyncio.get_running_loop()
        if self._use_local_fallback:
            return await loop.run_in_executor(None, self._download_local, key)

        try:
            response = await loop.run_in_executor(
                None,
                lambda: self._s3_client.get_object(  # type: ignore[union-attr]
                    Bucket=self._bucket, Key=key
                ),
            )
        except ClientError as exc:
            raise ObjectStorageUploadError(
                f"s3 get_object failed for {key}: {exc}"
            ) from exc
        body = response["Body"]
        return await loop.run_in_executor(None, body.read)

    async def upload_cleaned_stream(
        self,
        *,
        athlete_id: uuid.UUID,
        activity_id: uuid.UUID,
        payload_bytes: bytes,
        content_type: str = "application/gzip",
    ) -> StoredCleanedStream:
        """Upload a cleaned sensor stream to object storage."""
        key = self.build_cleaned_stream_key(athlete_id, activity_id)
        loop = asyncio.get_running_loop()

        if self._use_local_fallback:
            return await loop.run_in_executor(
                None, self._upload_local_cleaned_stream, key, payload_bytes
            )

        try:
            await loop.run_in_executor(
                None,
                lambda: self._s3_client.put_object(  # type: ignore[union-attr]
                    Bucket=self._bucket,
                    Key=key,
                    Body=payload_bytes,
                    ContentType=content_type,
                    Metadata={
                        "athlete_id": str(athlete_id),
                        "activity_id": str(activity_id),
                    },
                ),
            )
        except ClientError as exc:
            code: str = (
                cast(dict[str, Any], exc.response).get("Error", {}).get("Code", "")
            )
            if code in {"PreconditionFailed", "x-amz-precondition-failed"}:
                log_event(
                    event="object_storage.cleaned_stream.upload.conflict",
                    athlete_id=str(athlete_id),
                    outcome="failed",
                )
                raise ObjectStorageConflictError(
                    f"object already exists at {key}"
                ) from exc
            log_event(
                event="object_storage.cleaned_stream.upload.failed",
                athlete_id=str(athlete_id),
                outcome="failed",
            )
            raise ObjectStorageUploadError(
                f"s3 put_object failed for {key}: {exc}"
            ) from exc

        log_event(
            event="object_storage.cleaned_stream.upload.success",
            athlete_id=str(athlete_id),
            outcome="success",
        )
        return StoredCleanedStream(
            key=key,
            byte_count=len(payload_bytes),
            content_md5=md5_base64(payload_bytes),
        )

    async def download_cleaned_stream(self, key: str) -> bytes:
        """Download a previously-stored cleaned stream as raw bytes."""
        return await self.download_fit(key)

    async def exists(self, key: str) -> bool:
        """Return True if key exists in the configured bucket."""
        loop = asyncio.get_running_loop()
        if self._use_local_fallback:
            return await loop.run_in_executor(None, self._exists_local, key)

        try:
            await loop.run_in_executor(
                None,
                lambda: self._s3_client.head_object(  # type: ignore[union-attr]
                    Bucket=self._bucket, Key=key
                ),
            )
            return True
        except ClientError as exc:
            code: str = (
                cast(dict[str, Any], exc.response).get("Error", {}).get("Code", "")
            )
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise ObjectStorageUploadError(
                f"s3 head_object failed for {key}: {exc}"
            ) from exc

    def _upload_local(self, key: str, file_bytes: bytes) -> StoredFitObject:
        path = self.LOCAL_FALLBACK_ROOT / key
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise ObjectStorageConflictError(f"object already exists at {key}")
        with path.open("wb") as fh:
            fh.write(file_bytes)
        return StoredFitObject(
            key=key,
            byte_count=len(file_bytes),
            content_md5=md5_base64(file_bytes),
        )

    def _upload_local_cleaned_stream(
        self, key: str, file_bytes: bytes
    ) -> StoredCleanedStream:
        path = self.LOCAL_FALLBACK_ROOT / key
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise ObjectStorageConflictError(f"object already exists at {key}")
        with path.open("wb") as fh:
            fh.write(file_bytes)
        return StoredCleanedStream(
            key=key,
            byte_count=len(file_bytes),
            content_md5=md5_base64(file_bytes),
        )

    def _download_local(self, key: str) -> bytes:
        path = self.LOCAL_FALLBACK_ROOT / key
        if not path.is_file():
            raise ObjectStorageUploadError(f"object not found at {key}")
        return path.read_bytes()

    def _exists_local(self, key: str) -> bool:
        return (self.LOCAL_FALLBACK_ROOT / key).is_file()


_default_client: ObjectStorageClient | None = None


def get_object_storage_client() -> ObjectStorageClient:
    """Return the process-wide ObjectStorageClient."""
    global _default_client
    if _default_client is None:
        _default_client = ObjectStorageClient()
    return _default_client


def reset_object_storage_client() -> None:
    """Test helper — drop the process-wide client."""
    global _default_client
    _default_client = None


def md5_base64(data: bytes) -> str:
    """Return the base64-encoded MD5 digest."""
    import base64
    import hashlib

    return base64.b64encode(hashlib.md5(data).digest()).decode("ascii")
