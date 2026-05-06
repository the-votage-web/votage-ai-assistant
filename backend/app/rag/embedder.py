import time
import random
from typing import List, Dict
from openai import OpenAI

from app.db.config import settings

class OpenAIEmbedder:
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("Set OPENAI_API_KEY in environment variables.")
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model_id = settings.OPENAI_EMBED_MODEL

    def embed(self, text: str) -> List[float]:
        max_retries = 5
        base_delay = 1.0
        max_delay = 10.0
        for attempt in range(max_retries):
            try:
                response = self.client.embeddings.create(
                    model=self.model_id,
                    input=text
                )
                return response.data[0].embedding
            except Exception as e:
                error_text = str(e).lower()
                is_rate_limited = (
                    "rate limit" in error_text
                    or "429" in error_text
                    or "too many requests" in error_text
                )
                if is_rate_limited and attempt < max_retries - 1:
                    delay = min(max_delay, base_delay * (2 ** attempt)) + random.uniform(0, 0.3)
                    print(f"Embed rate-limited. Retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                raise e
        raise RuntimeError("Max retries exceeded for OpenAI embedding.")

    def embed_batch(self, chunks: List[Dict]) -> List[Dict]:
        """
        Adds embeddings to chunks
        """
        enriched = []

        for chunk in chunks:
            vector = self.embed(chunk["text"])

            enriched.append({
                **chunk,
                "embedding": vector
            })
            time.sleep(0.2)

        return enriched
