"""Paper library HTTP endpoints: upload, list, detail, annotations, collections."""

import pytest
from fastapi.testclient import TestClient

from backend.api.security import get_current_user
from backend.main import app

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n"


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u1",
        "username": "alice",
    }
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.integration
def test_upload_list_patch_and_annotate(client: TestClient):
    upload = client.post(
        "/papers",
        files={"file": ("attention.pdf", PDF_BYTES, "application/pdf")},
    )
    assert upload.status_code == 202, upload.text
    payload = upload.json()
    paper_id = payload["paper"]["id"]
    assert payload["paper"]["title"] == "attention"
    assert payload["document_status"] == "uploaded"
    assert payload["job_status"] == "queued"

    listing = client.get("/papers")
    assert listing.status_code == 200
    assert [row["id"] for row in listing.json()] == [paper_id]

    detail = client.get(f"/papers/{paper_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["primary_session_id"] == payload["session_id"]
    assert len(body["documents"]) == 1

    updated = client.patch(
        f"/papers/{paper_id}",
        json={"reading_status": "reading", "progress": 0.25, "tags": []},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["reading_status"] == "reading"
    assert updated.json()["progress"] == 0.25

    note = client.post(
        f"/papers/{paper_id}/annotations",
        json={"type": "note", "content": "important"},
    )
    assert note.status_code == 201, note.text
    annotation_id = note.json()["id"]
    assert client.get(f"/papers/{paper_id}/annotations").json()[0]["content"] == "important"

    edited = client.patch(
        f"/annotations/{annotation_id}", json={"content": "updated"}
    )
    assert edited.status_code == 200
    assert edited.json()["content"] == "updated"
    assert client.delete(f"/annotations/{annotation_id}").status_code == 200
    assert client.get(f"/papers/{paper_id}/annotations").json() == []


@pytest.mark.integration
def test_duplicate_upload_returns_existing_paper(client: TestClient):
    first = client.post(
        "/papers",
        files={"file": ("attention.pdf", PDF_BYTES, "application/pdf")},
    )
    assert first.status_code == 202
    second = client.post(
        "/papers",
        files={"file": ("attention-copy.pdf", PDF_BYTES, "application/pdf")},
    )
    assert second.status_code == 409
    assert second.json()["paper_id"] == first.json()["paper"]["id"]


@pytest.mark.integration
def test_collections_round_trip(client: TestClient):
    upload = client.post(
        "/papers",
        files={"file": ("attention.pdf", PDF_BYTES, "application/pdf")},
    )
    paper_id = upload.json()["paper"]["id"]

    created = client.post("/collections", json={"name": "Transformers"})
    assert created.status_code == 201
    collection_id = created.json()["id"]

    added = client.put(f"/collections/{collection_id}/papers/{paper_id}")
    assert added.status_code == 200
    collections = client.get("/collections").json()
    assert collections[0]["id"] == collection_id
    assert collections[0]["paper_count"] == 1

    detail = client.get(f"/papers/{paper_id}").json()
    assert [row["id"] for row in detail["collections"]] == [collection_id]

    assert client.delete(f"/collections/{collection_id}/papers/{paper_id}").status_code == 200
    assert client.get("/collections").json()[0]["paper_count"] == 0
