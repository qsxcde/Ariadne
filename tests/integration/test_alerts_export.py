"""Alert settings and BibTeX export."""

import pytest

from backend.application.library.export import export_bibtex, export_csl_json, export_markdown
from backend.application.reading.review import weekly_review
from backend.storage.sqlite import alerts as alert_repo
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import papers as paper_repo
from backend.storage.sqlite import sessions as session_repo


@pytest.mark.integration
def test_alert_settings_defaults_update_and_user_scope():
    default = alert_repo.get_or_create("u1")
    assert default["new_paper"] == 1
    assert default["digest_frequency"] == "weekly"

    updated = alert_repo.update(
        "u1", new_citation=1, digest_enabled=0, digest_frequency="daily"
    )
    assert updated["new_citation"] == 1
    assert updated["digest_enabled"] == 0
    assert updated["digest_frequency"] == "daily"

    other = alert_repo.get_or_create("u2")
    assert other["id"] != updated["id"]
    assert other["digest_frequency"] == "weekly"


@pytest.mark.integration
def test_bibtex_export_contains_metadata():
    session = session_repo.create_session("Bib", user_id="u1")
    document = document_repo.create_document(
        session_id=session["id"],
        filename="bib.pdf",
        file_path="/tmp/bib.pdf",
        mime_type="application/pdf",
        file_size=10,
    )
    paper_repo.update_paper_metadata(
        document["paper_id"],
        title="Attention Is All You Need",
        authors_json='["Vaswani", "Shazeer"]',
        year=2017,
        venue="NeurIPS",
        doi="10.1000/test",
    )

    bib = export_bibtex("u1")

    assert "@article{" in bib
    assert "Attention Is All You Need" in bib
    assert "Vaswani and Shazeer" in bib
    assert "NeurIPS" in bib
    assert export_bibtex("missing-user") == ""

    csl = export_csl_json("u1")
    assert csl[0]["title"] == "Attention Is All You Need"
    assert csl[0]["DOI"] == "10.1000/test"

    markdown = export_markdown("u1")
    assert "# Ariadne Library" in markdown
    assert "Attention Is All You Need" in markdown


@pytest.mark.integration
def test_weekly_review_is_digest_source():
    review = weekly_review("u1")
    assert review["read_papers"] == 0
    assert review["week_start"]
