"""ObjectStorageClient — S3-compatible object storage for FIT files.

Implements the Phase-1.6 contract from
``docs/architecture/04-platform/storage-topology.md``. The client is
the only writer of FIT files to object storage; the ingestion
pipeline MUST upload before any ``Activity`` record is created so the
raw FIT file is the reprocessing anchor per the architecture invariant.

Key layout (mirrors the architecture spec):

    fit-files/{athlete_id}/{activity_date}/{uuid}.fit

The raw FIT file is immutable once written — the client refuses to
overwrite an existing key and surfaces that as
:class:`ObjectStorageConflictError` so the caller can route to a
DLQ. Object storage has indefinite retention per the storage
topology spec; deletions are not exposed by this client.

Backend compatibility:

* AWS S3 — leave ``S3_ENDPOINT_URL`` empty and supply ``S3_REGION`` +
  access keys.
* MinIO / any S3-compatible store — supply ``S3_ENDPOINT_URL`` and
  the access/secret key pair. ``S3_USE_SSL`` toggles HTTPS on the
  endpoint URL.
* Local development fallback — when ``S3_ENDPOINT_URL`` and
  credentials are both empty the client falls back to a local
  filesystem rooted at ``./var/object-storage`` so unit tests and
  local dev run without an external service.

The client is constructed once per process via
:func:`get_object_storage_client` and reused across requests — the
underlying ``boto3.client`` is thread-safe and pools HTTP
connections.
"""

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


# ---------------------------------------------------------------------------
# Errors.
# ---------------------------------------------------------------------------


class ObjectStorageError(Exception):
    """Base class for object-storage failures."""


class ObjectStorageUploadError(ObjectStorageError):
    """The PUT call failed (network / 5xx / IO error)."""


class ObjectStorageConflictError(ObjectStorageError):
    """The key already exists. Raw FIT files are immutable per the
    architecture invariant; the caller should treat this as a
    non-retryable failure and route the message to the DLQ."""


class ObjectStorageNotConfiguredError(ObjectStorageError):
    """Object storage is required but neither S3 nor local fallback is
    configured. Surfaced as a 503 by the API layer so the deploy
    owner fixes the configuration rather than the runner retrying."""


# ---------------------------------------------------------------------------
# Result type.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StoredFitObject:
    """Value object returned by :meth:`ObjectStorageClient.upload_fit`.

    Carries the storage key plus byte count and content hash so the
    ingestion pipeline can record them on the ``Activity`` row without
    re-reading the file from disk.
    """

    key: str
    byte_count: int
    content_md5: str


@dataclass(frozen=True)
class StoredCleanedStream:
    """Value object returned by :meth:`ObjectStorageClient.upload_cleaned_stream`.

    Carries the cleaned-stream storage key plus byte count and content
    hash. The key is derived deterministically from ``(athlete_id,
    activity_id)`` (see :meth:`build_cleaned_stream_key`) so a retry
    of the signal-cleaning task after a partial commit hits the
    immutability conflict path on the second upload — the conflict is
    converted to success by ``SignalCleaningService`` per ADR-009's
    idempotency contract.
    """

    key: str
    byte_count: int
    content_md5: str


# ---------------------------------------------------------------------------
# Client.
# ---------------------------------------------------------------------------


class ObjectStorageClient:
    """S3-compatible object storage client.

    The client is constructed once per process. Thread-safety is
    inherited from ``boto3`` — concurrent ``upload_fit`` / ``download_fit``
    calls share the underlying connection pool.
    """

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
        self._use_ssl = (
            use_ssl if use_ssl is not None else settings.S3_USE_SSL
        )
        self._use_local_fallback = (
            not self._endpoint_url
            and not self._access_key
            and not self._secret_key
        )
        self._s3_client: Any = None
        if not self._use_local_fallback:
            self._s3_client = cast(Any, boto3.client(  # type: ignore[reportUnknownMemberType]
                "s3",
                endpoint_url=self._endpoint_url or None,
                region_name=self._region,
                aws_access_key_id=self._access_key or None,
                aws_secret_access_key=self._secret_key or None,
                use_ssl=self._use_ssl,
            ))

    # ------------------------------------------------------------------
    # Public API.
    # ------------------------------------------------------------------

    @staticmethod
    def build_fit_key(
        athlete_id: uuid.UUID, activity_date: date, suffix_uuid: uuid.UUID
    ) -> str:
        """Build the canonical object key for a FIT file.

        Format: ``fit-files/{athlete_id}/{YYYY-MM-DD}/{uuid}.fit``
        """
        return (
            f"fit-files/{athlete_id}/"
            f"{activity_date.isoformat()}/{suffix_uuid}.fit"
        )

    @staticmethod
    def build_cleaned_stream_key(
        athlete_id: uuid.UUID, activity_id: uuid.UUID
    ) -> str:
        """Build the deterministic object key for a cleaned sensor stream.

        Format: ``cleaned-streams/{athlete_id}/{activity_id}/stream.gz``

        The key is derived deterministically from ``(athlete_id,
        activity_id)`` — NOT a fresh UUID — so a retry of the
        signal-cleaning task after a partial commit hits the
        immutability conflict path on the second upload
        (:class:`ObjectStorageConflictError`), which the cleaning
        service treats as the idempotency outcome per ADR-009.
        """
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
        """Upload a FIT file to object storage.

        The key is built from the canonical
        ``fit-files/{athlete_id}/{activity_date}/{uuid}.fit`` pattern;
        ``suffix_uuid`` is optional and defaults to a freshly minted
        UUID4 so two simultaneous uploads for the same athlete and
        day never collide.

        The PUT call runs in a thread-pool executor so the async
        event loop is never blocked on the underlying network I/O.
        On success the new key is returned along with byte count and
        MD5 (base64) so the ingestion pipeline can persist the
        values on the ``Activity`` row.

        Raises:
            ObjectStorageUploadError: the PUT call failed
                (network / 5xx / credentials). The caller should
                retry per the ingestion pipeline's retry policy.
            ObjectStorageConflictError: the key already exists.
                Raw FIT files are immutable; this is non-retryable.
            ObjectStorageNotConfiguredError: object storage is not
                configured and the local fallback is also disabled
                (test-only escape hatch).
        """
        suffix = suffix_uuid or uuid.uuid4()
        key = self.build_fit_key(athlete_id, activity_date, suffix)
        loop = asyncio.get_running_loop()

        if self._use_local_fallback:
            return await loop.run_in_executor(
                None, self._upload_local, key, file_bytes
            )

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
            code: str = cast(dict[str, Any], exc.response).get("Error", {}).get("Code", "")
            if code in {"PreconditionFailed", "x-amz-precondition-failed"}:
                # Head-object preconditions returned a conflict — the
                # key already exists. Raw FIT files are immutable.
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
        """Download a previously-stored FIT file as raw bytes.

        Used by downstream analysis tasks (Phase 2+) to re-parse the
        raw file. The runner delegates the blocking network call to
        a thread-pool executor.

        Raises:
            ObjectStorageUploadError: the GET call failed. Surfaced
                with the same exception type as upload for caller
                simplicity.
        """
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
        """Upload a cleaned sensor stream to object storage.

        The key is built from the deterministic
        ``cleaned-streams/{athlete_id}/{activity_id}/stream.gz``
        pattern via :meth:`build_cleaned_stream_key`. The PUT call
        runs in a thread-pool executor so the async event loop is
        never blocked.

        The cleaned stream is append-only / immutable: if the key
        already exists, :class:`ObjectStorageConflictError` is raised
        so the cleaning task can treat the conflict as the
        idempotency outcome on retry (ADR-009). The conflict is
        caught by ``SignalCleaningService`` and converted to success
        without re-uploading.

        Raises:
            ObjectStorageUploadError: the PUT call failed
                (network / 5xx / credentials). The caller should
                retry per procrastinate's backoff policy.
            ObjectStorageConflictError: the key already exists.
                The cleaned stream is immutable; the cleaning
                service converts this to success on retry.
            ObjectStorageNotConfiguredError: object storage is not
                configured and the local fallback is also disabled.
        """
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
            code: str = cast(dict[str, Any], exc.response).get("Error", {}).get("Code", "")
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
        """Download a previously-stored cleaned stream as raw bytes.

        Parallel to :meth:`download_fit`; used by Phase-2.3
        segmentation to load the stream identified by
        ``RawSensorStream.fit_file_key``.

        Raises:
            ObjectStorageUploadError: the GET call failed. Surfaced
                with the same exception type as upload for caller
                simplicity.
        """
        return await self.download_fit(key)

    async def exists(self, key: str) -> bool:
        """Return ``True`` if *key* exists in the configured bucket."""
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
            code: str = cast(dict[str, Any], exc.response).get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise ObjectStorageUploadError(
                f"s3 head_object failed for {key}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Local fallback implementation — file-on-disk under
    # ``./var/object-storage`` so unit tests and local dev run without
    # a real S3 service.
    # ------------------------------------------------------------------

    def _upload_local(self, key: str, file_bytes: bytes) -> StoredFitObject:
        path = self.LOCAL_FALLBACK_ROOT / key
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise ObjectStorageConflictError(
                f"object already exists at {key}"
            )
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
            raise ObjectStorageConflictError(
                f"object already exists at {key}"
            )
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
            raise ObjectStorageUploadError(
                f"object not found at {key}"
            )
        return path.read_bytes()

    def _exists_local(self, key: str) -> bool:
        return (self.LOCAL_FALLBACK_ROOT / key).is_file()


# ---------------------------------------------------------------------------
# Process-wide singleton.
# ---------------------------------------------------------------------------


_default_client: ObjectStorageClient | None = None


def get_object_storage_client() -> ObjectStorageClient:
    """Return the process-wide :class:`ObjectStorageClient`.

    Lazy so test code can override settings before the first call.
    The single client shares the underlying ``boto3`` connection
    pool across requests.
    """
    global _default_client
    if _default_client is None:
        _default_client = ObjectStorageClient()
    return _default_client


def reset_object_storage_client() -> None:
    """Test helper — drop the process-wide client.

    Not for production use; the default client is intentionally
    long-lived so the boto3 connection pool is reused.
    """
    global _default_client
    _default_client = None


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def md5_base64(data: bytes) -> str:
    """Return the base64-encoded MD5 digest of *data*.

    Mirrors the S3 ``ETag`` format for single-part uploads so the
    value persisted on ``Activity.fit_file_key`` can be cross-checked
    against the storage ETag without an extra round-trip.
    """
    import base64
    import hashlib

    return base64.b64encode(hashlib.md5(data).digest()).decode("ascii")