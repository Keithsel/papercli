import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner

from papercli.db import Store
from papercli.models import Paper
from papercli.cli import app


@patch("requests.get")
def test_download_mullvad_rotation(mock_get):
    runner = CliRunner()

    mock_relays_resp = MagicMock()
    mock_relays_resp.json.return_value = {
        "wireguard": {
            "relays": [
                {"hostname": "us-dfw-wg-001", "active": True},
                {"hostname": "nl-ams-wg-001", "active": True},
            ]
        }
    }

    mock_pdf_resp = MagicMock()
    mock_pdf_resp.content = b"%PDF-1.4 mock content"

    mock_get.side_effect = [mock_relays_resp, mock_pdf_resp]

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "papers.db"
        store = Store(db_path)

        paper1 = Paper(
            title="Mullvad paper 1",
            authors=["Alice"],
            venue="ACL",
            year=2023,
            source="acl",
            pdf_url="http://example.com/paper1.pdf",
        )
        store.upsert([paper1])

        with (
            patch("papercli.download.Store", return_value=store),
            patch("papercli.download.DEFAULT_DB", db_path),
            patch("papercli.download.reorganize_pdfs"),
            patch("papercli.download.PDF_DIR", Path(tmpdir) / "pdfs"),
        ):
            result = runner.invoke(app, ["download", "--mullvad", "--delay", "0.0"])
            assert result.exit_code == 0
            assert "via" in result.stdout
            assert "socks5" in result.stdout

            conn = store.conn
            row = conn.execute(
                "SELECT pdf_path FROM papers WHERE id=?", (paper1.id,)
            ).fetchone()
            assert row["pdf_path"] is not None
            assert Path(row["pdf_path"]).exists()
