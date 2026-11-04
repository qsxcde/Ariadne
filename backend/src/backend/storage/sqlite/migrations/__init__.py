"""Schema migration entry point."""

from backend.storage.sqlite.migrations.versions import migrate_schema

__all__ = ["migrate_schema"]
