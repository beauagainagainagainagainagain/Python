"""
This is to show simple COVID19 info fetching from worldometers site using lxml
* The main motivation to use lxml in place of bs4 is that it is faster and therefore
more convenient to use in Python web projects (e.g. Django or Flask-based)
"""

from typing import NamedTuple

import requests
from lxml import html


class CovidData(NamedTuple):
    cases: int
    deaths: int
    recovered: int


def covid_stats(url: str = "https://www.worldometers.info/coronavirus/") -> CovidData:
    xpath_str = '//div[@class = "maincounter-number"]/span/text()'
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return CovidData(0, 0, 0)

    values = html.fromstring(response.content).xpath(xpath_str)
    try:
        cases, deaths, recovered = (
            int(value.replace(",", "")) for value in values[:3]
        )
    except (TypeError, ValueError):
        return CovidData(0, 0, 0)
    return CovidData(cases, deaths, recovered)


fmt = """Total COVID-19 cases in the world: {}
Total deaths due to COVID-19 in the world: {}
Total COVID-19 patients recovered in the world: {}"""


if __name__ == "__main__":
    print(fmt.format(*covid_stats()))
