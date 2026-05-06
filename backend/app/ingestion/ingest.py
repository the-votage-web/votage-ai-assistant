from dotenv import load_dotenv
load_dotenv()

from app.ingestion.pipeline import IngestionPipeline
from app.services.faq.faq import faq_service


def run():
    pipeline = IngestionPipeline(
        base_url="https://thevotagechurch.org"
    )

    md = pipeline.run()

    # 1. Save to file
    with open("app/data/faq.md", "w", encoding="utf-8") as f:
        f.write(md)
    print("💾 Markdown KB generated successfully")

    # 2. Index to pgvector
    print("🧠 Indexing to RAG database...")
    count = faq_service.build_index(md)
    print(f"✅ Indexed {count} Q&A pairs")


if __name__ == "__main__":
    run()