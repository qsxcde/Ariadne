"""Collection use cases with owner checks."""

from collections.abc import Mapping
from typing import Any

from backend.application.papers import get_accessible_paper
from backend.domain.exceptions import CollectionNotFoundError
from backend.storage.sqlite import collections as collection_repo


def _accessible(collection_id: str, user_id: str | None) -> dict[str, Any]:
    row = collection_repo.get_collection(collection_id)
    if row is None or row.get("user_id") not in (None, user_id):
        raise CollectionNotFoundError(
            f"Collection not found: {collection_id}", collection_id=collection_id
        )
    return dict(row)


def get_accessible_collection(
    collection_id: str, user_id: str | None
) -> dict[str, Any]:
    return _accessible(collection_id, user_id)


def list_for_user(user_id: str | None) -> list[dict[str, Any]]:
    return [
        _serialize(row)
        for row in collection_repo.list_collections(user_id)
    ]


def create_collection(
    user_id: str | None, *, name: str, description: str | None = None
) -> dict[str, Any]:
    row = collection_repo.create_collection(
        user_id=user_id, name=name, description=description
    )
    return _serialize(row)


def update_collection(
    collection_id: str,
    user_id: str | None,
    *,
    name: str | None = None,
    description: str | None = None,
    sort_order: int | None = None,
) -> dict[str, Any]:
    _accessible(collection_id, user_id)
    row = collection_repo.update_collection(
        collection_id, name=name, description=description, sort_order=sort_order
    )
    if row is None:
        raise CollectionNotFoundError(
            f"Collection not found: {collection_id}", collection_id=collection_id
        )
    return _serialize(row)


def add_paper(collection_id: str, paper_id: str, user_id: str | None) -> None:
    _accessible(collection_id, user_id)
    get_accessible_paper(paper_id, user_id)
    collection_repo.add_paper_to_collection(collection_id, paper_id)


def remove_paper(collection_id: str, paper_id: str, user_id: str | None) -> None:
    _accessible(collection_id, user_id)
    collection_repo.remove_paper_from_collection(collection_id, paper_id)


def _serialize(row: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(row)
    result["paper_count"] = len(collection_repo.list_collection_papers(row["id"]))
    return result
