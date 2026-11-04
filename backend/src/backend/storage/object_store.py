"""Object storage for session artifacts.

The database stores opaque references rather than assuming a local filesystem:

* ``local`` — an absolute path under the data directory (unchanged behaviour);
* ``s3`` — an object key such as ``raw/<session>/<document>.pdf``.

Readers call :meth:`ObjectStore.materialize` when a library needs a real path
(FAISS, pdfium) and :meth:`ObjectStore.get_bytes` otherwise.
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
from pathlib import Path
from typing import Any, Callable, Protocol

from backend import config

logger = logging.getLogger(__name__)

_BATCH_DELETE = 1000


class ObjectStore(Protocol):
    backend: str

    def ref(self, key: str) -> str: ...

    def put_bytes(self, key: str, data: bytes) -> str: ...

    def put_file(self, key: str, source: Path) -> str: ...

    def get_bytes(self, ref: str) -> bytes: ...

    def materialize(self, ref: str) -> Path: ...

    def exists(self, ref: str) -> bool: ...

    def delete(self, ref: str) -> None: ...

    def delete_prefix(self, prefix: str) -> None: ...


def _write_atomic(path: Path, write: Callable[[Path], object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        write(tmp)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


class LocalObjectStore:
    """Filesystem store rooted at the configured data directory."""

    backend = "local"

    def __init__(self, root: Path | None = None) -> None:
        self._root = (root or config.data_dir()).resolve()

    def _path(self, key: str) -> Path:
        candidate = Path(key)
        if not candidate.is_absolute():
            candidate = self._root / candidate
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self._root):
            raise ValueError(f"Object key escapes the data directory: {key}")
        return resolved

    def _ref_path(self, ref: str) -> Path:
        """Resolve a stored reference; legacy absolute paths may sit outside the root."""
        candidate = Path(ref).expanduser()
        if candidate.is_absolute():
            return candidate.resolve()
        return self._path(ref)

    def ref(self, key: str) -> str:
        return str(self._path(key))

    def put_bytes(self, key: str, data: bytes) -> str:
        path = self._path(key)
        _write_atomic(path, lambda tmp: tmp.write_bytes(data))
        return str(path)

    def put_file(self, key: str, source: Path) -> str:
        path = self._path(key)
        _write_atomic(path, lambda tmp: shutil.copyfile(source, tmp))
        return str(path)

    def get_bytes(self, ref: str) -> bytes:
        return self.materialize(ref).read_bytes()

    def materialize(self, ref: str) -> Path:
        path = self._ref_path(ref)
        if not path.is_file():
            raise FileNotFoundError(f"Object not found: {ref}")
        return path

    def exists(self, ref: str) -> bool:
        return self._ref_path(ref).is_file()

    def delete(self, ref: str) -> None:
        self._ref_path(ref).unlink(missing_ok=True)

    def delete_prefix(self, prefix: str) -> None:
        path = self._path(prefix)
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.is_file():
            path.unlink(missing_ok=True)


class S3ObjectStore:
    """S3-compatible store with a local materialization cache."""

    backend = "s3"

    def __init__(
        self,
        *,
        bucket: str,
        endpoint: str | None,
        access_key: str | None,
        secret_key: str | None,
        region: str,
        use_ssl: bool,
        cache_dir: Path | None = None,
        client: Any | None = None,
    ) -> None:
        self._bucket = bucket
        self._endpoint = endpoint or None
        self._access_key = access_key
        self._secret_key = secret_key
        self._region = region
        self._use_ssl = use_ssl
        self._cache_dir = (cache_dir or config.data_dir() / "object_cache").resolve()
        self._client = client
        self._lock = threading.Lock()

    def _client_or_create(self) -> Any:
        if self._client is not None:
            return self._client
        with self._lock:
            if self._client is None:
                import boto3
                from botocore.config import Config

                self._client = boto3.client(
                    "s3",
                    endpoint_url=self._endpoint,
                    aws_access_key_id=self._access_key,
                    aws_secret_access_key=self._secret_key,
                    region_name=self._region,
                    use_ssl=self._use_ssl,
                    config=Config(s3={"addressing_style": "path"}),
                )
            return self._client

    def ref(self, key: str) -> str:
        return self._clean_key(key)

    def put_bytes(self, key: str, data: bytes) -> str:
        clean = self._clean_key(key)
        self._client_or_create().put_object(
            Bucket=self._bucket, Key=clean, Body=data
        )
        self._invalidate_cache(clean)
        return clean

    def put_file(self, key: str, source: Path) -> str:
        clean = self._clean_key(key)
        self._client_or_create().upload_file(
            str(source), self._bucket, clean
        )
        self._invalidate_cache(clean)
        return clean

    def get_bytes(self, ref: str) -> bytes:
        legacy = self._legacy_path(ref)
        if legacy is not None:
            return legacy.read_bytes()
        return self.materialize(ref).read_bytes()

    def materialize(self, ref: str) -> Path:
        legacy = self._legacy_path(ref)
        if legacy is not None:
            return legacy
        clean = self._clean_key(ref)
        cached = self._cache_path(clean)
        etag = self._etag(clean)
        if etag is None:
            raise FileNotFoundError(f"Object not found: {ref}")
        marker = cached.with_name(cached.name + ".etag")
        if cached.is_file() and marker.is_file():
            try:
                if marker.read_text(encoding="utf-8") == etag:
                    return cached
            except OSError:
                pass
        cached.parent.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_name(cached.name + ".tmp")
        try:
            self._client_or_create().download_file(self._bucket, clean, str(tmp))
            os.replace(tmp, cached)
            marker.write_text(etag, encoding="utf-8")
        finally:
            tmp.unlink(missing_ok=True)
        return cached

    def exists(self, ref: str) -> bool:
        candidate = Path(ref)
        if candidate.is_absolute():
            resolved = self._absolute_ref(ref)
            return resolved.is_file()
        clean = self._clean_key(ref)
        return self._etag(clean) is not None

    def delete(self, ref: str) -> None:
        candidate = Path(ref)
        if candidate.is_absolute():
            self._absolute_ref(ref).unlink(missing_ok=True)
            return
        clean = self._clean_key(ref)
        self._client_or_create().delete_object(Bucket=self._bucket, Key=clean)
        self._invalidate_cache(clean)

    def delete_prefix(self, prefix: str) -> None:
        clean = self._clean_key(prefix).rstrip("/") + "/"
        client = self._client_or_create()
        token: str | None = None
        while True:
            params: dict[str, Any] = {"Bucket": self._bucket, "Prefix": clean}
            if token:
                params["ContinuationToken"] = token
            response = client.list_objects_v2(**params)
            keys = [{"Key": item["Key"]} for item in response.get("Contents", [])]
            for start in range(0, len(keys), _BATCH_DELETE):
                client.delete_objects(
                    Bucket=self._bucket,
                    Delete={"Objects": keys[start : start + _BATCH_DELETE]},
                )
            if not response.get("IsTruncated"):
                break
            token = response.get("NextContinuationToken")
            if not token:
                break
        cache_root = self._cache_dir / clean
        if cache_root.is_dir():
            shutil.rmtree(cache_root, ignore_errors=True)

    def _etag(self, key: str) -> str | None:
        from botocore.exceptions import ClientError

        try:
            response = self._client_or_create().head_object(
                Bucket=self._bucket, Key=key
            )
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise
        return str(response.get("ETag") or "")

    def _legacy_path(self, ref: str) -> Path | None:
        candidate = Path(ref)
        if not candidate.is_absolute():
            return None
        resolved = self._absolute_ref(ref)
        if not resolved.is_file():
            raise FileNotFoundError(f"Object not found: {ref}")
        return resolved

    @staticmethod
    def _absolute_ref(ref: str) -> Path:
        resolved = Path(ref).expanduser().resolve()
        root = config.data_dir().resolve()
        if not resolved.is_relative_to(root):
            raise ValueError(f"Object reference escapes the data directory: {ref}")
        return resolved

    def _cache_path(self, key: str) -> Path:
        target = (self._cache_dir / key).resolve()
        if not target.is_relative_to(self._cache_dir):
            raise ValueError(f"Object key escapes the cache directory: {key}")
        return target

    def _invalidate_cache(self, key: str) -> None:
        cached = self._cache_path(key)
        cached.unlink(missing_ok=True)
        cached.with_name(cached.name + ".etag").unlink(missing_ok=True)

    @staticmethod
    def _clean_key(key: str) -> str:
        parts = Path(key).as_posix().strip("/").split("/")
        if not parts or any(part in {"", ".", ".."} for part in parts):
            raise ValueError(f"Invalid object key: {key}")
        return "/".join(parts)


_store_lock = threading.Lock()
_store: ObjectStore | None = None
_store_key: tuple[str, str] | None = None


def get_object_store() -> ObjectStore:
    """Return the process-wide store; rebuilt when backend or data root changes."""
    global _store, _store_key
    backend = config.settings.object_store_backend
    key = (backend, str(config.data_dir().resolve()))
    with _store_lock:
        if _store is not None and _store_key == key:
            return _store
        if backend == "s3":
            _store = S3ObjectStore(
                bucket=config.settings.object_store_bucket,
                endpoint=config.settings.object_store_endpoint,
                access_key=config.settings.object_store_access_key,
                secret_key=config.settings.object_store_secret_key,
                region=config.settings.object_store_region,
                use_ssl=config.settings.object_store_use_ssl,
                cache_dir=_cache_dir(),
            )
        else:
            _store = LocalObjectStore()
        _store_key = key
        return _store


def reset_object_store() -> None:
    global _store, _store_key
    with _store_lock:
        _store = None
        _store_key = None


def _cache_dir() -> Path | None:
    configured = config.settings.object_store_cache_dir
    return Path(configured).expanduser() if configured else None
