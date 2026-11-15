"""Storage abstraction: local filesystem (dev) and S3-compatible (prod)."""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator

from .config import settings


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str) -> str:
    base = Path(name or "file").name
    cleaned = _SAFE_NAME.sub("_", base).strip("._") or "file"
    return cleaned[:180]


def build_key(*parts: str) -> str:
    """Build an object key, rejecting traversal attempts."""
    joined = "/".join(p.strip("/") for p in parts if p)
    if ".." in joined.split("/") or joined.startswith("/"):
        raise ValueError("Invalid storage key")
    return joined


class Storage:
    backend = "base"

    def put_file(self, local_path: Path, key: str, content_type: str = "application/octet-stream") -> str:
        raise NotImplementedError

    def put_bytes(self, data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
        raise NotImplementedError

    def open(self, key: str) -> BinaryIO:
        raise NotImplementedError

    def local_path(self, key: str) -> Path | None:
        return None

    def exists(self, key: str) -> bool:
        raise NotImplementedError

    def size(self, key: str) -> int:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def download_to(self, key: str, destination: Path) -> Path:
        raise NotImplementedError

    @contextmanager
    def temp_copy(self, key: str) -> Iterator[Path]:
        """Provide a local path for FFmpeg even when the backend is S3."""
        direct = self.local_path(key)
        if direct and direct.exists():
            yield direct
            return
        fd, tmp = tempfile.mkstemp(suffix=Path(key).suffix, dir=settings.data_dir / "tmp")
        os.close(fd)
        target = Path(tmp)
        try:
            self.download_to(key, target)
            yield target
        finally:
            target.unlink(missing_ok=True)


class LocalStorage(Storage):
    backend = "local"

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or settings.data_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        key = build_key(key)
        target = (self.root / key).resolve()
        if self.root not in target.parents and target != self.root:
            raise ValueError("Path traversal blocked")
        return target

    def put_file(self, local_path: Path, key: str, content_type: str = "application/octet-stream") -> str:
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if Path(local_path).resolve() != target:
            shutil.move(str(local_path), str(target))
        return key

    def put_bytes(self, data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return key

    def open(self, key: str) -> BinaryIO:
        return open(self._resolve(key), "rb")

    def local_path(self, key: str) -> Path | None:
        return self._resolve(key)

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    def size(self, key: str) -> int:
        try:
            return self._resolve(key).stat().st_size
        except FileNotFoundError:
            return 0

    def delete(self, key: str) -> None:
        target = self._resolve(key)
        if target.is_file():
            target.unlink(missing_ok=True)
            if target.parent != self.root:
                try:
                    target.parent.rmdir()
                except OSError:
                    pass

    def download_to(self, key: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self._resolve(key), destination)
        return destination

    def new_temp_path(self, suffix: str = "") -> Path:
        name = f"{uuid.uuid4().hex}{suffix}"
        return self.root / "tmp" / name


class S3Storage(Storage):
    backend = "s3"

    def __init__(self) -> None:
        import boto3  # imported lazily so local dev needs no AWS SDK
        from botocore.config import Config

        if not settings.s3_bucket:
            raise RuntimeError("S3_BUCKET must be set when STORAGE_BACKEND=s3")
        self.bucket = settings.s3_bucket
        self.prefix = settings.s3_prefix.strip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key or None,
            aws_secret_access_key=settings.s3_secret_key or None,
            config=Config(signature_version="s3v4"),
        )

    def _key(self, key: str) -> str:
        key = build_key(key)
        return f"{self.prefix}/{key}" if self.prefix else key

    def put_file(self, local_path: Path, key: str, content_type: str = "application/octet-stream") -> str:
        self.client.upload_file(
            str(local_path), self.bucket, self._key(key), ExtraArgs={"ContentType": content_type}
        )
        return key

    def put_bytes(self, data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
        self.client.put_object(Bucket=self.bucket, Key=self._key(key), Body=data, ContentType=content_type)
        return key

    def open(self, key: str) -> BinaryIO:
        response = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
        return response["Body"]

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(key))
            return True
        except Exception:
            return False

    def size(self, key: str) -> int:
        try:
            return int(self.client.head_object(Bucket=self.bucket, Key=self._key(key))["ContentLength"])
        except Exception:
            return 0

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._key(key))

    def download_to(self, key: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, self._key(key), str(destination))
        return destination


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = S3Storage() if settings.storage_backend.lower() == "s3" else LocalStorage()
    return _storage
