from pathlib import Path
from unittest.mock import patch, MagicMock
from papercli.crawlers.openreview import _value
from papercli.crawlers.cvf import CVFCrawler

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_openreview_value_helper():
    assert _value({"title": {"value": "Super Model"}}, "title") == "Super Model"

    assert _value({"title": "Super Model"}, "title") == "Super Model"

    assert _value({"authors": ["Alice", "Bob"]}, "authors") == ["Alice", "Bob"]

    assert _value({}, "missing") is None
    assert _value({"empty": None}, "empty") is None


@patch("requests.get")
def test_cvf_crawler_sibling_walk(mock_get):
    mock_html = _read("cvf_sibling_walk.html")
    mock_response = MagicMock()
    mock_response.text = mock_html
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    crawler = CVFCrawler()
    papers = list(crawler.fetch("CVPR", 2025))

    assert len(papers) == 2

    paper1 = papers[0]
    assert paper1.title == "Dynamic Sibling Walk Paper"
    assert paper1.authors == ["Author A", "Author B"]
    assert (
        paper1.pdf_url
        == "https://openaccess.thecvf.com/content/CVPR2025/papers/Test_Paper_CVPR_2025_paper.pdf"
    )
    assert (
        paper1.forum_url
        == "https://openaccess.thecvf.com/content/CVPR2025/html/Test_Paper_CVPR_2025_paper.html"
    )

    paper2 = papers[1]
    assert paper2.title == "Next Paper Title"
    assert paper2.authors == ["Author C"]
    assert (
        paper2.pdf_url
        == "https://openaccess.thecvf.com/content/CVPR2025/papers/Another_Paper_CVPR_2025_paper.pdf"
    )
    assert (
        paper2.forum_url
        == "https://openaccess.thecvf.com/content/CVPR2025/html/Another_Paper_CVPR_2025_paper.html"
    )
