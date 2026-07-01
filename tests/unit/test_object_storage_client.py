"""Unit tests for ObjectStorageClient.

Tests upload_fit, download_fit, exists with local filesystem fallback.
S3 operations are tested via mocking.

Reference: docs/implementation/phase-1/phase-1-6-p1-simple-fit-import.md
docs/implementation/phase-1/phase-1-7-p1-architecture-simplification.md
"""

from __future__ import annotations

import tempfile
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.services.object_storage_client import (
    ObjectStorageClient,
    ObjectStorageConflictError,
    ObjectStorageError,
    ObjectStorageNotConfiguredError,
    ObjectStorageUploadError,
    StoredFitObject,
    _md5_base64,
)


class TestBuildFitKey:
    """Static build_fit_key method."""

    def test_format(self) -> None:
        athlete_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        activity_date = date(2026, 6, 15)
        suffix = uuid.UUID("00000000-0000-0000-0000-000000000002")
        key = ObjectStorageClient.build_fit_key(athlete_id, activity_date, suffix)
        assert key == "fit-files/00000000-0000-0000-0000-000000000001/2026-06-15/00000000-0000-0000-0000-000000000002.fit"

    def test_suffix_uuid_in_key(self) -> None:
        athlete_id = uuid.uuid4()
        activity_date = date(2026, 6, 15)
        suffix = uuid.uuid4()
        key = ObjectStorageClient.build_fit_key(athlete_id, activity_date, suffix)
        assert str(suffix) in key


class TestLocalFallbackUpload:
    """Local filesystem fallback when no S3 config is set."""

    def _client(self, root: Path | None = None) -> ObjectStorageClient:
        """Create client with local fallback enabled."""
        return ObjectStorageClient(
            endpoint_url=None,
            access_key=None,
            secret_key=None,
        )

    @pytest.mark.asyncio
    async def test_upload_fit_creates_file_on_disk(self) -> None:
        """upload_fit writes bytes to the local fallback root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = ObjectStorageClient(
                endpoint_url=None, access_key=None, secret_key=None
            )
            # Override the fallback root to our temp directory
            client.LOCAL_FALLBACK_ROOT = Path(tmpdir)

            athlete_id = uuid.uuid4()
            activity_date = date(2026, 6, 15)
            file_bytes = b"fake fit file content"

            result = await client.upload_fit(
                athlete_id=athlete_id,
                activity_date=activity_date,
                file_bytes=file_bytes,
            )

            assert isinstance(result, StoredFitObject)
            assert result.key.startswith("fit-files/")
            assert result.byte_count == len(file_bytes)
            assert result.content_md5 is not None

            # Verify file exists on disk
            path = Path(tmpdir) / result.key
            assert path.exists()
            assert path.read_bytes() == file_bytes

    @pytest.mark.asyncio
    async def test_upload_fit_conflict_raises_error(self) -> None:
        """Uploading to an existing key raises ObjectStorageConflictError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = ObjectStorageClient(
                endpoint_url=None, access_key=None, secret_key=None
            )
            client.LOCAL_FALLBACK_ROOT = Path(tmpdir)

            athlete_id = uuid.uuid4()
            activity_date = date(2026, 6, 15)
            suffix_uuid = uuid.uuid4()
            file_bytes = b"first upload"

            # First upload succeeds
            await client.upload_fit(
                athlete_id=athlete_id,
                activity_date=activity_date,
                file_bytes=file_bytes,
                suffix_uuid=suffix_uuid,
            )

            # Second upload with same suffix raises conflict
            with pytest.raises(ObjectStorageConflictError):
                await client.upload_fit(
                    athlete_id=athlete_id,
                    activity_date=activity_date,
                    file_bytes=b"second upload",
                    suffix_uuid=suffix_uuid,
                )

    @pytest.mark.asyncio
    async def test_download_fit_returns_bytes(self) -> None:
        """download_fit reads bytes from the local fallback root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = ObjectStorageClient(
                endpoint_url=None, access_key=None, secret_key=None
            )
            client.LOCAL_FALLBACK_ROOT = Path(tmpdir)

            athlete_id = uuid.uuid4()
            activity_date = date(2026, 6, 15)
            suffix_uuid = uuid.uuid4()
            file_bytes = b"download test content"

            # First upload
            result = await client.upload_fit(
                athlete_id=athlete_id,
                activity_date=activity_date,
                file_bytes=file_bytes,
                suffix_uuid=suffix_uuid,
            )

            # Download and verify
            downloaded = await client.download_fit(result.key)
            assert downloaded == file_bytes

    @pytest.mark.asyncio
    async def test_download_fit_nonexistent_raises_error(self) -> None:
        """download_fit raises ObjectStorageUploadError when key not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = ObjectStorageClient(
                endpoint_url=None, access_key=None, secret_key=None
            )
            client.LOCAL_FALLBACK_ROOT = Path(tmpdir)

            with pytest.raises(ObjectStorageUploadError) as exc_info:
                await client.download_fit("nonexistent/key.fit")
            assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_exists_true_when_file_present(self) -> None:
        """exists returns True when the key exists in local fallback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = ObjectStorageClient(
                endpoint_url=None, access_key=None, secret_key=None
            )
            client.LOCAL_FALLBACK_ROOT = Path(tmpdir)

            athlete_id = uuid.uuid4()
            activity_date = date(2026, 6, 15)
            suffix_uuid = uuid.uuid4()
            file_bytes = b"exists test"

            result = await client.upload_fit(
                athlete_id=athlete_id,
                activity_date=activity_date,
                file_bytes=file_bytes,
                suffix_uuid=suffix_uuid,
            )

            exists = await client.exists(result.key)
            assert exists is True

    @pytest.mark.asyncio
    async def test_exists_false_when_file_absent(self) -> None:
        """exists returns False when the key does not exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = ObjectStorageClient(
                endpoint_url=None, access_key=None, secret_key=None
            )
            client.LOCAL_FALLBACK_ROOT = Path(tmpdir)

            exists = await client.exists("nonexistent/key.fit")
            assert exists is False

    @pytest.mark.asyncio
    async def test_upload_fit_returns_stored_fit_object(self) -> None:
        """upload_fit returns StoredFitObject with key, byte_count, content_md5."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = ObjectStorageClient(
                endpoint_url=None, access_key=None, secret_key=None
            )
            client.LOCAL_FALLBACK_ROOT = Path(tmpdir)

            athlete_id = uuid.uuid4()
            activity_date = date(2026, 6, 15)
            file_bytes = b"stored fit object test"

            result = await client.upload_fit(
                athlete_id=athlete_id,
                activity_date=activity_date,
                file_bytes=file_bytes,
            )

            assert isinstance(result, StoredFitObject)
            assert result.key.startswith("fit-files/")
            assert result.byte_count == len(file_bytes)
            assert result.content_md5 == _md5_base64(file_bytes)

    @pytest.mark.asyncio
    async def test_creates_nested_directories(self) -> None:
        """upload_fit creates nested directories if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = ObjectStorageClient(
                endpoint_url=None, access_key=None, secret_key=None
            )
            client.LOCAL_FALLBACK_ROOT = Path(tmpdir)

            athlete_id = uuid.uuid4()
            activity_date = date(2026, 6, 15)

            await client.upload_fit(
                athlete_id=athlete_id,
                activity_date=activity_date,
                file_bytes=b"nested dir test",
            )

            # The path should exist after upload
            key_prefix = f"fit-files/{athlete_id}/2026-06-15/"
            # Check that at least one file was created under the expected path.
            # Use relative path comparison — rglob returns absolute paths, so
            # str(p) is like "/tmp/xyz/fit-files/..." which does NOT start with
            # the relative key_prefix "fit-files/...".
            found = False
            for p in Path(tmpdir).rglob("*.fit"):
                if str(p.relative_to(Path(tmpdir))).startswith(key_prefix):
                    found = True
                    break
            assert found, "Expected nested directory structure not found"


class TestS3Upload:
    """S3 upload operations (mocked)."""

    @pytest.mark.asyncio
    async def test_upload_fit_s3_success(self) -> None:
        """Successful S3 upload returns StoredFitObject."""
        client = ObjectStorageClient(
            endpoint_url="http://minio:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
            bucket="test-bucket",
        )

        mock_s3 = pytest.importorskip("boto3").client.return_value
        mock_s3.put_object.return_value = {}

        athlete_id = uuid.uuid4()
        activity_date = date(2026, 6, 15)
        file_bytes = b"s3 upload test"

        with patch.object(client, "_s3_client", mock_s3):
            result = await client.upload_fit(
                athlete_id=athlete_id,
                activity_date=activity_date,
                file_bytes=file_bytes,
            )

        assert isinstance(result, StoredFitObject)
        assert result.key.startswith("fit-files/")
        mock_s3.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_fit_s3_conflict(self) -> None:
        """S3 PreconditionFailed error raises ObjectStorageConflictError."""
        from botocore.exceptions import ClientError

        client = ObjectStorageClient(
            endpoint_url="http://minio:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
        )

        mock_error_response = {
            "Error": {"Code": "PreconditionFailed"}
        }
        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = ClientError(mock_error_response, "PutObject")

        with patch.object(client, "_s3_client", mock_s3):
            with pytest.raises(ObjectStorageConflictError):
                await client.upload_fit(
                    athlete_id=uuid.uuid4(),
                    activity_date=date(2026, 6, 15),
                    file_bytes=b"conflict test",
                )

    @pytest.mark.asyncio
    async def test_download_fit_s3(self) -> None:
        """S3 download returns bytes."""
        client = ObjectStorageClient(
            endpoint_url="http://minio:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
        )

        mock_body = MagicMock()
        mock_body.read.return_value = b"downloaded fit content"
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": mock_body}

        with patch.object(client, "_s3_client", mock_s3):
            result = await client.download_fit("fit-files/athlete/date/uuid.fit")

        assert result == b"downloaded fit content"

    @pytest.mark.asyncio
    async def test_exists_s3_true(self) -> None:
        """S3 head_object returns True when key exists."""
        client = ObjectStorageClient(
            endpoint_url="http://minio:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
        )

        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {}

        with patch.object(client, "_s3_client", mock_s3):
            result = await client.exists("fit-files/athlete/date/uuid.fit")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_s3_false_404(self) -> None:
        """S3 head_object returns False when key returns 404."""
        from botocore.exceptions import ClientError

        client = ObjectStorageClient(
            endpoint_url="http://minio:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
        )

        mock_error_response = {"Error": {"Code": "404"}}
        mock_s3 = MagicMock()
        mock_s3.head_object.side_effect = ClientError(mock_error_response, "HeadObject")

        with patch.object(client, "_s3_client", mock_s3):
            result = await client.exists("nonexistent/key.fit")

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_s3_other_error_raises(self) -> None:
        """S3 head_object raises ObjectStorageUploadError for non-404 errors."""
        from botocore.exceptions import ClientError

        client = ObjectStorageClient(
            endpoint_url="http://minio:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
        )

        mock_error_response = {"Error": {"Code": "500"}}
        mock_s3 = MagicMock()
        mock_s3.head_object.side_effect = ClientError(mock_error_response, "HeadObject")

        with patch.object(client, "_s3_client", mock_s3):
            with pytest.raises(ObjectStorageUploadError):
                await client.exists("error/key.fit")


class TestMd5Base64:
    """_md5_base64 helper."""

    def test_returns_base64_string(self) -> None:
        import base64
        result = _md5_base64(b"hello")
        # MD5 of "hello" in base64
        assert isinstance(result, str)
        # Verify it's valid base64
        decoded = base64.b64decode(result)
        assert len(decoded) == 16  # MD5 produces 16 bytes

    def test_deterministic(self) -> None:
        result1 = _md5_base64(b"test")
        result2 = _md5_base64(b"test")
        assert result1 == result2

    def test_different_inputs_different_hashes(self) -> None:
        result1 = _md5_base64(b"test1")
        result2 = _md5_base64(b"test2")
        assert result1 != result2


class TestStoredFitObject:
    """StoredFitObject is a frozen dataclass."""

    def test_frozen(self) -> None:
        obj = StoredFitObject(key="test.fit", byte_count=100, content_md5="abc123")
        with pytest.raises(AttributeError):
            obj.key = "changed.fit"  # type: ignore

    def test_equality(self) -> None:
        a = StoredFitObject(key="test.fit", byte_count=100, content_md5="abc123")
        b = StoredFitObject(key="test.fit", byte_count=100, content_md5="abc123")
        assert a == b