import json
import re
import uuid
import time
from typing import Any

from langchain_core.documents import Document
from sqlalchemy import create_engine, text

from app.db.config import settings
from typing import Optional, Any, Dict, Tuple, List, Any
from app.rag.embeddings import embed  # your Bedrock Titan embedding



_TOKEN_RE = re.compile(r"[a-zA-Z0-9']+")


def _tokens(value: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(value or "") if len(t) > 2}


class PostgresRAGStore:
    def __init__(self, collection_name: str):
        self.collection_name = collection_name
        self.engine = create_engine(settings.DATABASE_URL, future=True)
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self.engine.begin() as conn:
            # 1. Enable pgvector extension
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

            # 2. Create main RAG table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS rag_documents (
                    id UUID PRIMARY KEY,
                    collection_name VARCHAR(120) NOT NULL,
                    page_content TEXT NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    embedding VECTOR(1536),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """))

            # 3. Index for filtering by collection
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_rag_documents_collection_name
                ON rag_documents (collection_name);
            """))

            # 4. JSONB index for metadata filtering
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_rag_documents_metadata_gin
                ON rag_documents USING GIN (metadata);
            """))

            # 5. Vector index (HNSW is often better than IVF Flat for small/medium sets)
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_rag_documents_embedding
                ON rag_documents
                USING hnsw (embedding vector_cosine_ops);
            """))

    def add_documents(self, docs: list[Document]) -> None:
        if not docs:
            return

        with self.engine.begin() as conn:
            for doc in docs:
                doc_id = str(uuid.uuid4())

                vector = embed(doc.page_content)

                conn.execute(text("""
                    INSERT INTO rag_documents
                    (id, collection_name, page_content, metadata, embedding)
                    VALUES (:id, :collection_name, :page_content, :metadata, :embedding)
                """), {
                    "id": doc_id,
                    "collection_name": self.collection_name,
                    "page_content": doc.page_content,
                    "metadata": json.dumps(doc.metadata or {}),
                    "embedding": vector
                })
                # Small sleep to avoid hitting rate limits too aggressively
                time.sleep(0.5)

    
    def _metadata_where_clause(self, where: Optional[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
        if not where:
            return "", {}

        clauses: list[str] = []
        params: dict[str, Any] = {}
        for idx, (key, value) in enumerate(where.items()):
            param_key = f"meta_value_{idx}"
            clauses.append(f"metadata ->> '{key}' = :{param_key}")
            params[param_key] = str(value)

        return " AND " + " AND ".join(clauses), params

    def get(
        self,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        extra_where, meta_params = self._metadata_where_clause(where)
        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT id
                    FROM rag_documents
                    WHERE collection_name = :collection_name
                    {extra_where}
                    """
                ),
                {"collection_name": self.collection_name, **meta_params},
            ).mappings().all()

        return {"ids": [str(r["id"]) for r in rows]}

    def delete(self, ids: list[str]) -> None:
        if not ids:
            return

        with self.engine.begin() as conn:
            for raw_id in ids:
                conn.execute(
                    text(
                        """
                        DELETE FROM rag_documents
                        WHERE collection_name = :collection_name
                          AND id = CAST(:id AS uuid)
                        """
                    ),
                    {"collection_name": self.collection_name, "id": raw_id},
                )

    def similarity_search(self, query: str, k: int = 4, filter=None):
        q_vector = embed(query)

        extra_where, meta_params = self._metadata_where_clause(filter)

        with self.engine.begin() as conn:
            rows = conn.execute(text(f"""
            SELECT id, page_content, metadata
            FROM rag_documents
            WHERE collection_name = :collection_name
            {extra_where}
            ORDER BY embedding <=> :vector
            LIMIT :k
        """), {
            "collection_name": self.collection_name,
            "vector": q_vector,
            "k": k,
            **meta_params
        }).mappings().all()

            results = []
            for row in rows:
                results.append(Document(
                    page_content=row["page_content"],
                    metadata=row["metadata"] or {}
                ))

            return results
        

def members_store():
    return PostgresRAGStore(collection_name=settings.MEMBERS_COLLECTION)


def docs_store():
    return PostgresRAGStore(collection_name=settings.DOCS_COLLECTION)

