from app.ingestion.scraper import CuratedScraper
from app.ingestion.md_builder import MarkdownBuilder

class IngestionPipeline:
    """
    Pure deterministic ingestion:
    Scraper → Markdown → RAG
    """

    def __init__(self, base_url: str):
        self.scraper = CuratedScraper(
            base_url=base_url,
            paths=[
                "/home",
                "/connect",
                "/about",
                "/sermons",
                "/growth-track"
            ]
        )
        self.builder = MarkdownBuilder()

    def run(self):
        print("🚀 Starting ingestion pipeline...")

        scraped_pages = self.scraper.scrape()
        return self.builder.build(scraped_pages)
