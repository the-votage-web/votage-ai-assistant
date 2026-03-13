import json
import re
import uuid
from typing import Any

from langchain_core.documents import Document
from sqlalchemy import create_engine, text

from app.core.config import settings
from typing import Optional, Any, Dict, Tuple


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
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS rag_documents (
                        id UUID PRIMARY KEY,
                        collection_name VARCHAR(120) NOT NULL,
                        page_content TEXT NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_rag_documents_collection_name "
                    "ON rag_documents (collection_name)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_rag_documents_metadata_gin "
                    "ON rag_documents USING GIN (metadata)"
                )
            )

    def add_documents(self, docs: list[Document]) -> None:
        if not docs:
            return

        with self.engine.begin() as conn:
            for doc in docs:
                doc_id = str(uuid.uuid4())
                conn.execute(
                    text(
                        """
                        INSERT INTO rag_documents (id, collection_name, page_content, metadata)
                        VALUES (CAST(:id AS uuid), :collection_name, :page_content, CAST(:metadata AS jsonb))
                        """
                    ),
                    {
                        "id": doc_id,
                        "collection_name": self.collection_name,
                        "page_content": doc.page_content,
                        "metadata": json.dumps(doc.metadata or {}),
                    },
                )

    
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

    def get(self, where: dict[str, Any] | None = None, include: list[str] | None = None) -> dict[str, Any]:
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

    def similarity_search(self, query: str, k: int = 4, filter: dict[str, Any] | None = None) -> list[Document]:
        extra_where, meta_params = self._metadata_where_clause(filter)
        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT id, page_content, metadata
                    FROM rag_documents
                    WHERE collection_name = :collection_name
                    {extra_where}
                    ORDER BY created_at DESC
                    LIMIT 500
                    """
                ),
                {"collection_name": self.collection_name, **meta_params},
            ).mappings().all()

        q = query or ""
        q_tokens = _tokens(q)
        q_lower = q.lower().strip()

        scored: list[tuple[int, dict[str, Any]]] = []
        for row in rows:
            content = row["page_content"] or ""
            content_tokens = _tokens(content)
            overlap = len(q_tokens.intersection(content_tokens))
            substring_bonus = 2 if q_lower and q_lower in content.lower() else 0
            score = overlap * 3 + substring_bonus
            scored.append((score, row))

        scored.sort(key=lambda item: item[0], reverse=True)
        top_rows = [row for _, row in scored[: max(1, k)]]

        results: list[Document] = []
        for row in top_rows:
            metadata = row["metadata"]
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except Exception:
                    metadata = {}
            results.append(Document(page_content=row["page_content"], metadata=metadata or {}))

        return results

    def persist(self) -> None:
        # No-op for PostgreSQL-backed store.
        return


def members_store():
    return PostgresRAGStore(collection_name=settings.MEMBERS_COLLECTION)


def docs_store():
    return PostgresRAGStore(collection_name=settings.DOCS_COLLECTION)
