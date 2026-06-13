import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from papercli.base import _venue_year_key
from papercli.db import Store
from papercli.models import Paper


def test_venue_year_key():
    assert _venue_year_key(("AAAI", 2024)) == ("aaai", "aaai", 2024)
    assert _venue_year_key(("ACL", 2023)) == ("acl", "acl", 2023)
    assert _venue_year_key(("CVPR", 2025)) == ("cvf", "cvpr", 2025)

    items = [("CVPR", 2025), ("ACL", 2023), ("AAAI", 2024)]
    sorted_items = sorted(items, key=_venue_year_key)
    assert sorted_items == [("AAAI", 2024), ("ACL", 2023), ("CVPR", 2025)]


@patch("huggingface_hub.HfApi")
def test_sync_hf_logic(mock_hf_api_class):
    mock_api = MagicMock()
    mock_hf_api_class.return_value = mock_api

    mock_info = MagicMock()
    mock_info.sha = "dummy-sha-123"
    mock_api.repo_info.return_value = mock_info

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "papers.db"
        store = Store(db_path)

        paper1 = Paper(
            title="A dummy paper",
            authors=["Alice"],
            venue="ACL",
            year=2023,
            source="acl",
            pdf_url="http://example.com/paper.pdf",
        )
        store.upsert([paper1])

        expected_pdf_path = f"pdfs/acl/2023/{paper1.id[:2]}/{paper1.id}.pdf"
        mock_api.list_repo_files.return_value = [expected_pdf_path]

        with (
            patch("papercli.cli.Store", return_value=store),
            patch("papercli.cli.DEFAULT_DB", db_path),
        ):
            from papercli.cli import _sync_hf_logic

            conn = store.conn
            row = conn.execute(
                "SELECT pdf_path FROM papers WHERE id=?", (paper1.id,)
            ).fetchone()
            assert not row["pdf_path"]

            _sync_hf_logic()

            row = conn.execute(
                "SELECT pdf_path FROM papers WHERE id=?", (paper1.id,)
            ).fetchone()
            assert row["pdf_path"] == f"hf://{expected_pdf_path}"


@patch("huggingface_hub.HfApi")
@patch("huggingface_hub.create_repo")
def test_sync_hf_logic_creates_missing_repo(mock_create_repo, mock_hf_api_class):
    from huggingface_hub.errors import RepositoryNotFoundError
    import httpx

    mock_api = MagicMock()
    mock_hf_api_class.return_value = mock_api

    mock_info = MagicMock()
    mock_info.sha = "dummy-sha-456"
    mock_response = httpx.Response(
        404, request=httpx.Request("GET", "https://huggingface.co")
    )
    mock_api.repo_info.side_effect = [
        RepositoryNotFoundError("Repo not found", response=mock_response),
        mock_info,
    ]
    mock_api.list_repo_files.return_value = []

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "papers.db"
        store = Store(db_path)

        paper1 = Paper(
            title="A dummy paper",
            authors=["Alice"],
            venue="ACL",
            year=2023,
            source="acl",
            pdf_url="http://example.com/paper.pdf",
        )
        store.upsert([paper1])

        with (
            patch("papercli.cli.Store", return_value=store),
            patch("papercli.cli.DEFAULT_DB", db_path),
        ):
            from papercli.cli import _sync_hf_logic

            _sync_hf_logic()

    mock_create_repo.assert_called_once()
    args, kwargs = mock_create_repo.call_args
    repo_id_arg = kwargs.get("repo_id") if "repo_id" in kwargs else args[0]
    assert repo_id_arg == "ClosedUni/papercli-papers-acl"


def test_upsert_does_not_overwrite_pdf_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "papers.db"
        store = Store(db_path)

        paper1 = Paper(
            title="A dummy paper",
            authors=["Alice"],
            venue="ACL",
            year=2023,
            source="acl",
            pdf_url="http://example.com/paper.pdf",
        )
        store.upsert([paper1])

        store.set_pdf_path(paper1.id, "/path/to/local.pdf")

        store.upsert([paper1])

        conn = store.conn
        row = conn.execute(
            "SELECT pdf_path FROM papers WHERE id=?", (paper1.id,)
        ).fetchone()
        assert row["pdf_path"] == "/path/to/local.pdf"


def test_venue_years_filtering():
    from typer.testing import CliRunner
    from papercli.cli import app, console

    console.width = 150

    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "papers.db"
        store = Store(db_path)

        with (
            patch("papercli.cli.Store", return_value=store),
            patch("papercli.cli.DEFAULT_DB", db_path),
            patch(
                "papercli.cli.all_supported_venue_years",
                return_value=[("CVPR", 2024), ("ICLR", 2025), ("NeurIPS", 2025)],
            ),
        ):
            result = runner.invoke(app, ["venue-years"])
            assert result.exit_code == 0
            assert "CVPR" in result.stdout
            assert "ICLR" in result.stdout
            assert "NeurIPS" in result.stdout

            result_inc = runner.invoke(app, ["venue-years", "--include", "CVPR,2025"])
            assert result_inc.exit_code == 0
            assert "CVPR" in result_inc.stdout
            assert "ICLR" in result_inc.stdout
            assert "NeurIPS" in result_inc.stdout

            result_inc_cvpr = runner.invoke(app, ["venue-years", "--include", "CVPR"])
            assert result_inc_cvpr.exit_code == 0
            assert "CVPR" in result_inc_cvpr.stdout
            assert "ICLR" not in result_inc_cvpr.stdout
            assert "NeurIPS" not in result_inc_cvpr.stdout

            result_exc = runner.invoke(app, ["venue-years", "--exclude", "NeurIPS"])
            assert result_exc.exit_code == 0
            assert "CVPR" in result_exc.stdout
            assert "ICLR" in result_exc.stdout
            assert "NeurIPS" not in result_exc.stdout

            result_both = runner.invoke(
                app,
                ["venue-years", "--include", "2025", "--exclude", "NeurIPS"],
            )
            assert result_both.exit_code == 0
            assert "CVPR" not in result_both.stdout
            assert "ICLR" in result_both.stdout
            assert "NeurIPS" not in result_both.stdout
