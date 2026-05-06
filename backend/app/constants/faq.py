import re

FAQ_SESSION_START_TOKENS = {
    "faq",
    "start faq",
    "faq session",
    "start faq session",
    "start qna",
}

FAQ_SESSION_END_TOKENS = {
    "exit faq",
    "end faq",
    "stop faq",
    "close faq",
}

FAQ_BLOCK_RE = re.compile(
    r"Q:\s*(?P<question>.+?)\nA:\s*(?P<answer>.+?)(?=\nQ:|\n##\s+Sources|\Z)",
    re.DOTALL,
)

STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "is",
    "are", "do", "does", "did", "what", "who", "where", "when", "why", "how",
    "your", "you", "about", "know", "tell", "me",
}

GREETING_TOKENS = {
    "hi",
    "hello",
    "hey",
    "good morning",
    "good afternoon",
    "good evening",
}
