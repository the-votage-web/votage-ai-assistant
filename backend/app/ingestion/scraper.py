import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


class CuratedScraper:
    def __init__(self, base_url: str, paths: list[str]):
        self.base_url = base_url.rstrip("/")
        self.paths = paths

    def fetch(self, url: str):
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.text

    def clean(self, html: str):
        soup = BeautifulSoup(html, "html.parser")

        # remove noise
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n")

        lines = [l.strip() for l in text.splitlines()]
        lines = [l for l in lines if len(l) > 0]

        return "\n".join(lines)

    def scrape(self):
        data = {}

        for path in self.paths:
            url = urljoin(self.base_url, path)

            print(f"📄 Scraping: {url}")

            html = self.fetch(url)
            clean_text = self.clean(html)

            data[path] = clean_text

        return data