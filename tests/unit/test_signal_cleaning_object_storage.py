"""Unit tests for ObjectStorageClient cleaned-stream methods.

Tests build_cleaned_stream_key, upload_cleaned_stream, and
download_cleaned_stream following the same patterns as the existing
fit-file tests in test_object_storage_client.py.

Reference: docs/implementation/phase-2/phase-2-2-p1-signal-cleaning.md
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from app.services.object_storage_client import (
    ObjectStorageClient,
    ObjectStorageConflictError,
    ObjectStorageUploadError,
    StoredCleanedStream,
)


class TestBuildCleanedStreamKey:
    """Static build_cleaned_stream_key method."""

    def test_format(self) -> None:
        """Key matches the exact pattern
        cleaned-streams/{athlete_id}/{activity_id}/stream.gz."""
        athlete_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        activity_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
        key = ObjectStorageClient.build_cleaned_stream_key(athlete_id, activity_id)
        assert key == "cleaned-streams/00000000-0000-0000-0000-000000000001/00000000-0000-0000-0000-000000000002/stream.gz"

    def test_deterministic(self) -> None:
        """Same (athlete_id, activity_id) always produces the same key."""
        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()
        key1 = ObjectStorageClient.build_cleaned_stream_key(athlete_id, activity_id)
        key2 = ObjectStorageClient.build_cleaned_stream_key(athlete_id, activity_id)
        assert key1 == key2

    def test_different_inputs_different_keys(self) -> None:
        """Different athlete_id or activity_id produces a different key."""
        athlete_id = uuid.uuid4()
        activity_id_1 = uuid.uuid4()
        activity_id_2 = uuid.uuid4()
        key1 = ObjectStorageClient.build_cleaned_stream_key(athlete_id, activity_id_1)
        key2 = ObjectStorageClient.build_cleaned_stream_key(athlete_id, activity_id_2)
        assert key1 != key2

    def test_no_fit_in_key(self) -> None:
        """The cleaned-stream key does not contain 'fit-files' so it
        cannot collide with the raw FIT key."""
        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()
        key = ObjectStorageClient.build_cleaned_stream_key(athlete_id, activity_id)
        assert "fit-files" not in key
        assert key.startswith("cleaned-streams/")


class TestLocalFallbackCleanedStream:
    """Local filesystem fallback for cleaned-stream operations."""

    @pytest.mark.asyncio
    async def test_upload_cleaned_stream_creates_file_on_disk(self) -> None:
        """upload_cleaned_stream writes bytes to the local fallback root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = ObjectStorageClient(
                endpoint_url=None, access_key=None, secret_key=None
            )
            client.LOCAL_FALLBACK_ROOT = Path(tmpdir)

            athlete_id = uuid.uuid4()
            activity_id = uuid.uuid4()
            payload = b"fake gzip cleaned stream"

            result = await client.upload_cleaned_stream(
                athlete_id=athlete_id,
                activity_id=activity_id,
                payload_bytes=payload,
            )

            assert isinstance(result, StoredCleanedStream)
            expected_key = f"cleaned-streams/{athlete_id}/{activity_id}/stream.gz"
            assert result.key == expected_key
            assert result.byte_count == len(payload)
            assert result.content_md5 is not None

            # Verify file exists on disk.
            path = Path(tmpdir) / expected_key
            assert path.exists()
            assert path.read_bytes() == payload

    @pytest.mark.asyncio
    async def test_upload_cleaned_stream_conflict_raises_error(self) -> None:
        """Uploading to an existing cleaned-stream key raises
        ObjectStorageConflictError — the immutability semantics
        parallel upload_fit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = ObjectStorageClient(
                endpoint_url=None, access_key=None, secret_key=None
            )
            client.LOCAL_FALLBACK_ROOT = Path(tmpdir)

            athlete_id = uuid.uuid4()
            activity_id = uuid.uuid4()
            payload1 = b"first upload"
            payload2 = b"second upload"

            # First upload succeeds.
            await client.upload_cleaned_stream(
                athlete_id=athlete_id,
                activity_id=activity_id,
                payload_bytes=payload1,
            )

            # Second upload to the same key raises conflict.
            with pytest.raises(ObjectStorageConflictError):
                await client.upload_cleaned_stream(
                    athlete_id=athlete_id,
                    activity_id=activity_id,
                    payload_bytes=payload2,
                )

    @pytest.mark.asyncio
    async def test_download_cleaned_stream_returns_bytes(self) -> None:
        """download_cleaned_stream reads previously-uploaded bytes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = ObjectStorageClient(
                endpoint_url=None, access_key=None, secret_key=None
            )
            client.LOCAL_FALLBACK_ROOT = Path(tmpdir)

            athlete_id = uuid.uuid4()
            activity_id = uuid.uuid4()
            payload = b"downloaded cleaned stream"

            key = f"cleaned-streams/{athlete_id}/{activity_id}/stream.gz"
            (Path(tmpdir) / key).parent.mkdir(parents=True, exist_ok=True)
            (Path(tmpdir) / key).write_bytes(payload)

            result = await client.download_cleaned_stream(key)
            assert result == payload

    @pytest.mark.asyncio
    async def test_download_cleaned_stream_nonexistent_raises_error(self) -> None:
        """download_cleaned_stream raises ObjectStorageUploadError
        when the key is not found in local fallback.

        Note: ``ObjectStorageConflictError`` is for PUT conflicts
        (key already exists) and is intentionally not raised on a
        missing GET. The local-fallback path surfaces a missing
        key as ``ObjectStorageUploadError``; the S3 path catches
        ``ClientError`` and re-raises the same class for caller
        simplicity (see app/services/object_storage_client.py
        :meth:`download_fit`/:meth:`download_cleaned_stream` and
        :meth:`_download_local`).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            client = ObjectStorageClient(
                endpoint_url=None, access_key=None, secret_key=None
            )
            client.LOCAL_FALLBACK_ROOT = Path(tmpdir)

            with pytest.raises(ObjectStorageUploadError):
                await client.download_cleaned_stream("cleaned-streams/nonexistent/activity/stream.gz")


class TestS3CleanedStream:
    """S3 operations for cleaned streams (mocked)."""

    @pytest.mark.asyncio
    async def test_upload_cleaned_stream_s3_success(self) -> None:
        """Successful S3 upload returns StoredCleanedStream."""
        client = ObjectStorageClient(
            endpoint_url="http://minio:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
            bucket="test-bucket",
        )

        mock_s3 = MagicMock()
        mock_s3.put_object.return_value = {}

        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()
        payload = b"s3 cleaned stream"

        with patch.object(client, "_s3_client", mock_s3):
            result = await client.upload_cleaned_stream(
                athlete_id=athlete_id,
                activity_id=activity_id,
                payload_bytes=payload,
            )

        assert isinstance(result, StoredCleanedStream)
        expected_key = f"cleaned-streams/{athlete_id}/{activity_id}/stream.gz"
        assert result.key == expected_key
        mock_s3.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_cleaned_stream_s3_conflict(self) -> None:
        """S3 PreconditionFailed error raises ObjectStorageConflictError."""
        from botocore.exceptions import ClientError

        client = ObjectStorageClient(
            endpoint_url="http://minio:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
        )

        mock_error_response = {"Error": {"Code": "PreconditionFailed"}}
        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = ClientError(
            cast(Any, mock_error_response), "PutObject"
        )

        with patch.object(client, "_s3_client", mock_s3):
            with pytest.raises(ObjectStorageConflictError):
                await client.upload_cleaned_stream(
                    athlete_id=uuid.uuid4(),
                    activity_id=uuid.uuid4(),
                    payload_bytes=b"conflict test",
                )


class TestStoredCleanedStream:
    """StoredCleanedStream is a frozen dataclass."""

    def test_frozen(self) -> None:
        obj = StoredCleanedStream(
            key="cleaned-streams/ath/act/stream.gz",
            byte_count=100,
            content_md5="abc123",
        )
        with pytest.raises(AttributeError):
            obj.key = "changed.gz"  # type: ignore

    def test_equality(self) -> None:
        a = StoredCleanedStream(key="k", byte_count=100, content_md5="abc")
        b = StoredCleanedStream(key="k", byte_count=100, content_md5="abc")
        assert a == b