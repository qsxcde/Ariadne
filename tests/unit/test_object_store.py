import hashlib
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from backend.storage.object_store import LocalObjectStore, S3ObjectStore


class _FakeBody:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


class _FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.downloads: list[str] = []

    def put_object(self, *, Bucket: str, Key: str, Body) -> None:
        data = Body.read() if hasattr(Body, "read") else bytes(Body)
        self.objects[Key] = data

    def upload_file(self, Filename: str, Bucket: str, Key: str) -> None:
        self.objects[Key] = Path(Filename).read_bytes()

    def head_object(self, *, Bucket: str, Key: str) -> dict:
        self._missing(Key, "HeadObject")
        digest = hashlib.md5(self.objects[Key]).hexdigest()
        return {"ETag": f'"{digest}"'}

    def download_file(self, Bucket: str, Key: str, Filename: str) -> None:
        self._missing(Key, "GetObject")
        Path(Filename).write_bytes(self.objects[Key])
        self.downloads.append(Key)

    def delete_object(self, *, Bucket: str, Key: str) -> None:
        self.objects.pop(Key, None)

    def list_objects_v2(self, *, Bucket: str, Prefix: str, **_) -> dict:
        keys = sorted(key for key in self.objects if key.startswith(Prefix))
        return {
            "Contents": [{"Key": key} for key in keys],
            "IsTruncated": False,
        }

    def delete_objects(self, *, Bucket: str, Delete: dict) -> None:
        for item in Delete["Objects"]:
            self.objects.pop(item["Key"], None)

    def _missing(self, key: str, operation: str) -> None:
        if key not in self.objects:
            raise ClientError(
                {"Error": {"Code": "404", "Message": "Not Found"}}, operation
            )


def _s3_store(tmp_path: Path, client: _FakeS3) -> S3ObjectStore:
    return S3ObjectStore(
        bucket="ariadne",
        endpoint="http://127.0.0.1:9000",
        access_key="test",
        secret_key="test",
        region="us-east-1",
        use_ssl=False,
        cache_dir=tmp_path / "cache",
        client=client,
    )


def test_local_store_round_trip_and_prefix_delete(tmp_path):
    store = LocalObjectStore(root=tmp_path / "data")

    ref = store.put_bytes("raw/s1/doc.pdf", b"%PDF-1.7")
    assert Path(ref).read_bytes() == b"%PDF-1.7"
    assert store.materialize(ref).is_file()
    assert store.get_bytes(ref) == b"%PDF-1.7"
    assert store.ref("raw/s1/doc.pdf") == ref

    store.put_file("raw/s1/parsed/doc/document.md", _file(tmp_path / "source.md", b"# hi"))
    assert store.exists("raw/s1/parsed/doc/document.md")

    store.delete_prefix("raw/s1")
    assert not (tmp_path / "data" / "raw" / "s1").exists()
    assert not store.exists(ref)


def test_local_store_rejects_keys_outside_root(tmp_path):
    store = LocalObjectStore(root=tmp_path / "data")
    with pytest.raises(ValueError):
        store.put_bytes("../escape.txt", b"x")


def test_local_store_reads_legacy_absolute_paths_outside_root(tmp_path):
    outside = _file(tmp_path / "legacy.pdf", b"%PDF-legacy")
    store = LocalObjectStore(root=tmp_path / "data")

    assert store.get_bytes(str(outside)) == b"%PDF-legacy"
    assert store.exists(str(outside))
    store.delete(str(outside))
    assert not outside.exists()


def test_s3_store_round_trip_and_cache_invalidation(tmp_path):
    client = _FakeS3()
    store = _s3_store(tmp_path, client)

    ref = store.put_bytes("raw/s1/doc.pdf", b"first")
    assert ref == "raw/s1/doc.pdf"
    assert store.get_bytes(ref) == b"first"
    assert store.materialize(ref).read_bytes() == b"first"
    assert client.downloads == ["raw/s1/doc.pdf"]

    assert store.get_bytes(ref) == b"first"
    assert client.downloads == ["raw/s1/doc.pdf"]

    store.put_bytes("raw/s1/doc.pdf", b"second")
    assert store.get_bytes(ref) == b"second"
    assert client.downloads == ["raw/s1/doc.pdf", "raw/s1/doc.pdf"]


def test_s3_store_put_file_and_delete_prefix(tmp_path):
    client = _FakeS3()
    store = _s3_store(tmp_path, client)

    store.put_bytes("index/s1/snapshots/a.faiss.index", b"a")
    store.put_bytes("index/s1/snapshots/a.chunks.json", b"b")
    store.put_bytes("index/s2/snapshots/b.faiss.index", b"c")
    store.put_file("index/s1/snapshots/c.faiss.index", _file(tmp_path / "c", b"d"))

    assert store.exists("index/s1/snapshots/c.faiss.index")
    store.delete_prefix("index/s1/snapshots")
    assert not store.exists("index/s1/snapshots/a.faiss.index")
    assert not store.exists("index/s1/snapshots/a.chunks.json")
    assert not store.exists("index/s1/snapshots/c.faiss.index")
    assert store.exists("index/s2/snapshots/b.faiss.index")


def test_s3_store_missing_object_is_reported_as_not_found(tmp_path):
    store = _s3_store(tmp_path, _FakeS3())
    assert store.exists("raw/s1/missing.pdf") is False
    with pytest.raises(FileNotFoundError):
        store.get_bytes("raw/s1/missing.pdf")


def test_s3_store_rejects_invalid_keys(tmp_path):
    store = _s3_store(tmp_path, _FakeS3())
    with pytest.raises(ValueError):
        store.put_bytes("../escape", b"x")


def _file(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path
