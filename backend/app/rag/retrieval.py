from rag.store import PostgresRAGStore

store = PostgresRAGStore(collection_name="docs")


def retrieve(query: str, k: int = 5):
    return store.similarity_search(query, k=k)