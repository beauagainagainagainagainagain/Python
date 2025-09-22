import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web_programming.covid_stats_via_xpath import CovidData, covid_stats


def test_covid_stats_returns_default_on_error(monkeypatch):
    def fake_get(url, timeout):  # noqa: ARG001 - signature matches requests.get
        raise requests.exceptions.Timeout

    monkeypatch.setattr(requests, "get", fake_get)
    assert covid_stats("http://example.com") == CovidData(0, 0, 0)


def test_covid_stats_parses_values(monkeypatch):
    html_content = """
    <div class="maincounter-number"><span>1,234</span></div>
    <div class="maincounter-number"><span>56</span></div>
    <div class="maincounter-number"><span>7</span></div>
    """.encode()

    class FakeResponse:
        def __init__(self, content):
            self.content = content

        def raise_for_status(self):
            return None

    monkeypatch.setattr(requests, "get", lambda url, timeout: FakeResponse(html_content))
    assert covid_stats("http://example.com") == CovidData(1234, 56, 7)
