"""S3-compatible backend (AWS S3, MinIO) built on boto3.

boto3 ships in the ``s3`` extra: ``pip install forensicwace-core[s3]``.
Path-style addressing is forced because MinIO does not resolve
virtual-hosted bucket subdomains out of the box.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

from ..exceptions import ConfigurationError, StorageError

_DELETE_BATCH = 1000  # DeleteObjects API hard limit


class S3ObjectStorage:
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str | None = None,
    ):
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # pragma: no cover - depends on install extras
            raise ConfigurationError(
                "boto3 is not installed — install forensicwace-core[s3] to use object storage"
            ) from exc

        self.bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region or "us-east-1",
            config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
        )

    def ensure_bucket(self) -> None:
        from botocore.exceptions import ClientError

        try:
            self._client.head_bucket(Bucket=self.bucket)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") not in ("404", "NoSuchBucket"):
                raise StorageError(f"Object storage unreachable: {exc}") from exc
            try:
                self._client.create_bucket(Bucket=self.bucket)
            except ClientError as create_exc:
                raise StorageError(f"Cannot create bucket {self.bucket!r}: {create_exc}") from create_exc

    def put_fileobj(self, key: str, fileobj: BinaryIO) -> None:
        try:
            self._client.upload_fileobj(fileobj, self.bucket, key)
        except Exception as exc:
            raise StorageError(f"Upload of {key!r} failed: {exc}") from exc

    def get_file(self, key: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._client.download_file(self.bucket, key, str(dest))
        except Exception as exc:
            raise StorageError(f"Download of {key!r} failed: {exc}") from exc

    def iter_keys(self, prefix: str) -> Iterator[str]:
        try:
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    yield obj["Key"]
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f"Listing {prefix!r} failed: {exc}") from exc

    def delete_prefix(self, prefix: str) -> int:
        keys = list(self.iter_keys(prefix))
        try:
            for start in range(0, len(keys), _DELETE_BATCH):
                batch = keys[start : start + _DELETE_BATCH]
                self._client.delete_objects(
                    Bucket=self.bucket,
                    Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True},
                )
        except Exception as exc:
            raise StorageError(f"Deletion under {prefix!r} failed: {exc}") from exc
        return len(keys)
