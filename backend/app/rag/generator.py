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

        prompt = f"""You are a warm, friendly assistant for The Votage church, talking with website visitors. Always sound welcoming and kind.

The CONTEXT below is the church's full knowledge base — a set of question/answer pairs. Read across ALL of it and connect related entries.

Decide how to respond to the QUESTION:

1. CHURCH-SPECIFIC facts about The Votage (service times, location, leaders, events, dates, giving/amounts, programs, ministries, groups, or church policies):
   - If the CONTEXT covers it, answer using ONLY the context. Read across all entries and combine related ones. Match partial, shortened, or informal names to the fuller item — e.g. "connect" -> "Connect Group"; "refresh" -> the church's Refresh offerings such as the Refresh Miracle Service and the Refresh Tour; asking about "church" time -> the service times; "growth track" -> the membership / Growth Track class.
   - Only if the church's knowledge base genuinely does not cover the topic at all, do NOT guess — reply with EXACTLY: I don't have enough information.

2. GENERAL or common-sense questions that are NOT specific to The Votage (e.g. what to wear to church in general, general etiquette, broadly Christian questions):
   - Give a warm, brief, faith-appropriate general answer. Do not present it as official Votage policy unless it is in the CONTEXT.

3. PERSONAL or PASTORAL questions (counselling, emotional support, prayer requests, personal spiritual advice, crisis, grief, relationships, finances, health, or anything that needs a caring human):
   - Do NOT try to counsel or advise. Reply with EXACTLY: I don't have enough information.

CONTEXT:
{context_text}

QUESTION:
{question}

ANSWER:"""

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
