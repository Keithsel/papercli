from pathlib import Path

from papercli.crawlers.cvf import CVFCrawler
from papercli.crawlers.jmlr import JMLRCrawler
from papercli.crawlers.ijcai import IJCAICrawler

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_cvf_parse():
    papers = list(CVFCrawler()._parse(_read("cvf.html"), "WACV", 2024))
    assert len(papers) == 2

    foo = papers[0]
    assert foo.title == "Foo: A Method"
    assert foo.authors == ["Alice Smith", "Bob Jones"]
    assert (
        foo.pdf_url
        == "https://openaccess.thecvf.com/content/WACV2024/papers/Foo_paper.pdf"
    )
    assert foo.venue == "WACV" and foo.year == 2024 and foo.source == "cvf"

    bar = papers[1]
    assert bar.authors == ["Carol White"]
    assert bar.pdf_url.endswith("Bar_paper.pdf")


def test_jmlr_parse():
    papers = list(JMLRCrawler()._parse(_read("jmlr.html"), "JMLR", 2024))
    assert len(papers) == 2
    assert papers[0].title == "On Truthing Issues"
    assert papers[0].authors == ["Jonathan K. Su"]
    assert papers[0].pdf_url == "https://jmlr.org/papers/volume25/19-301/19-301.pdf"
    assert papers[1].authors == ["Yuze Han", "Guangzeng Xie", "Zhihua Zhang"]


def test_ijcai_parse():
    papers = list(IJCAICrawler()._parse(_read("ijcai.html"), "IJCAI", 2024))
    assert len(papers) == 2
    p0 = papers[0]
    assert p0.title == "Certified Policy Verification"
    assert p0.authors == ["S. Akshay", "Krishnendu Chatterjee"]
    assert p0.pdf_url == "https://www.ijcai.org/proceedings/2024/0001.pdf"
    assert p0.forum_url == "https://www.ijcai.org/proceedings/2024/1"
