import time
import random
from typing import List, Dict
from openai import OpenAI

from app.db.config import settings

class OpenAIGenerator:
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("Set OPENAI_API_KEY in environment variables.")
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model_id = settings.OPENAI_CHAT_MODEL

    def generate(self, question: str, context: List[Dict]) -> str:
        context_text = "\n\n".join(
            [f"Q: {c['question']}\nA: {c['answer']}" for c in context]
        )

        prompt = f"""You are a helpful assistant for The Votage church FAQ.

Use the context below (question/answer pairs from the church's knowledge base) to answer
the user's question. You may combine and rephrase across the pairs, as long as everything
you say is supported by the context.

Rules:
- Base your answer only on the context. Do NOT use outside knowledge or invent details.
- If the context contains nothing that addresses the user's question (the topic simply
  isn't covered), reply with EXACTLY this sentence and nothing else:
  I don't have enough information.

Context:
{context_text}

Question:
{question}

Answer:"""

        max_retries = 5
        base_delay = 1.0
        max_delay = 10.0
        
        for attempt in range(max_retries):
            try:
                response = self.client.responses.create(
                    model=self.model_id,
                    input=prompt,
                    max_output_tokens=400,
                    temperature=0.3,
                )
                return response.output_text
            except Exception as e:
                error_text = str(e).lower()
                is_rate_limited = (
                    "rate limit" in error_text
                    or "429" in error_text
                    or "too many requests" in error_text
                )
                if is_rate_limited and attempt < max_retries - 1:
                    delay = min(max_delay, base_delay * (2 ** attempt)) + random.uniform(0, 0.3)
                    print(f"Generator rate-limited. Retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                raise e
        
        raise RuntimeError("Max retries exceeded for OpenAI generation.")
