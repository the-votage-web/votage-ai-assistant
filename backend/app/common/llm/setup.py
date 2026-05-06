
import os
import re
from dotenv import load_dotenv
from app.common.llm.schemas import Extracted
from langchain_core.prompts import ChatPromptTemplate

try:
    from langchain_aws.chat_models import ChatBedrock
except Exception:
    ChatBedrock = None

load_dotenv()  # loads API key and other env vars


PHONE_RE = re.compile(r"\b0\d{10}\b")
_BEDROCK_THROTTLE_COOLDOWN_SECONDS = int(os.getenv("BEDROCK_THROTTLE_COOLDOWN_SECONDS", "600"))
CHECKIN_LLM_PROVIDER = os.getenv("CHECKIN_LLM_PROVIDER", "bedrock").strip().lower()


_bedrock_model_id = os.getenv("BEDROCK_PROFILE_ARN") or os.getenv("BEDROCK_MODEL_ID")
_bedrock_provider = os.getenv("BEDROCK_PROVIDER", "anthropic")

llm = None
structured_llm = None
if ChatBedrock and _bedrock_model_id:
    llm = ChatBedrock(
        model_id=_bedrock_model_id,
        region_name=os.getenv("AWS_REGION"),
        provider=_bedrock_provider,
    )
    structured_llm = llm.with_structured_output(Extracted)

extract_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are an AI church assistant. Extract the user's intent and fields.\n"
     "Extract the user's intent and fields. Follow the schema exactly.If a field is missing, return null.\n"
     "{{intent: one of [checkin, first_timer, faq, update_profile, unknown], "
     "phone?: string, full_name?: string, sunday_code?: string, question?: string, "
     "service_type?: one of [sunday_service, connect, special_service]}}\n"
     "Rules:\n"
     "- If user wants to mark attendance -> intent=checkin.\n"
     "- If user says first time/new -> intent=first_timer.\n"
     "- If user asks church info -> intent=faq and put the question.\n"
     "- If user mentions updating phone/name -> intent=update_profile.\n"
     "- If user mentions sunday/connect/special service during checkin, extract service_type.\n"
    ),
    ("user", "{message}")
])

RAG_PROMPT = """
You are a church assistant.

Answer ONLY using the context below.

If the answer is not in the context, say:
"I don't know. Please contact church admin."

Context:
{context}

Question:
{question}
"""
