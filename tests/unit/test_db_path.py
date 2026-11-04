"""Where the SQLite file lives.

Runtime state must not land inside the installed package: it would show up as
untracked files and could be committed with a database containing user rows.
"""

import pytest

from backend import config
from backend.storage.sqlite import connection


@pytest.mark.unit
def test_default_db_path_is_inside_the_data_dir(monkeypatch):
    monkeypatch.setattr(config.settings, "ariadne_db_path", None)
    monkeypatch.setattr(config.settings, "ariadne_data_dir", None)

    path = connection.get_db_path()

    assert path == config.default_data_dir() / "ariadne.db"
    assert path.parent.name == "data"
    assert "src" not in path.parts


@pytest.mark.unit
def test_explicit_db_path_wins(monkeypatch, tmp_path):
    target = tmp_path / "custom.db"
    monkeypatch.setattr(config.settings, "ariadne_db_path", str(target))

    assert connection.get_db_path() == target
