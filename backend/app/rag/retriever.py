import psycopg2
from typing import List, Dict
import json


class PgVectorRetriever:
    def __init__(self, db_config):
        """
        Accepts either a DSN string or a dictionary of connection parameters.
        """
        self.db_config = db_config
        self.conn = self._connect()

    def _connect(self):
        if isinstance(self.db_config, str):
            return psycopg2.connect(self.db_config)
        return psycopg2.connect(**self.db_config)

    def _ensure_conn(self):
        # Neon (and Postgres) drop idle connections; reconnect if ours is dead.
        if self.conn is None or self.conn.closed:
            self.conn = self._connect()

    # -------------------------
    # STORE EMBEDDINGS
    # -------------------------
    def store_vectors(self, chunks: List[Dict]):
        """
        Inserts Q&A chunks into pgvector table
        """

        try:
            self._ensure_conn()
            with self.conn.cursor() as cur:
                for chunk in chunks:
                    vector_literal = self._to_vector_literal(chunk["embedding"])
                    cur.execute(
                        """
                        INSERT INTO faq_embeddings (id, question, answer, text, embedding, metadata)
                        VALUES (%s, %s, %s, %s, %s::vector, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (
                            chunk["id"],
                            chunk["question"],
                            chunk["answer"],
                            chunk["text"],
                            vector_literal,
                            json.dumps(chunk.get("metadata", {}))
                        )
                    )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def upsert_vector(self, chunk: Dict):
        """Insert or replace a single vector row (used for live admin KB edits).

        Reconnects and retries once if Neon has dropped the idle connection
        (same self-healing behaviour as ``search``).
        """
        last_exc = None
        for attempt in range(2):
            try:
                self._ensure_conn()
                with self.conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO faq_embeddings (id, question, answer, text, embedding, metadata)
                        VALUES (%s, %s, %s, %s, %s::vector, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            question = EXCLUDED.question,
                            answer = EXCLUDED.answer,
                            text = EXCLUDED.text,
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata
                        """,
                        (
                            chunk["id"],
                            chunk["question"],
                            chunk["answer"],
                            chunk["text"],
                            self._to_vector_literal(chunk["embedding"]),
                            json.dumps(chunk.get("metadata", {})),
                        ),
                    )
                self.conn.commit()
                return
            except (psycopg2.InterfaceError, psycopg2.OperationalError) as exc:
                # Stale/broken connection — drop it, reconnect, and retry once.
                last_exc = exc
                try:
                    self.conn.close()
                except Exception:
                    pass
                self.conn = self._connect()
            except Exception:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                raise
        raise last_exc

    def delete_vector(self, vector_id: str):
        """Remove a single vector row by id (used when an admin deletes a KB entry).

        Reconnects and retries once on a stale Neon connection.
        """
        last_exc = None
        for attempt in range(2):
            try:
                self._ensure_conn()
                with self.conn.cursor() as cur:
                    cur.execute("DELETE FROM faq_embeddings WHERE id = %s", (vector_id,))
                self.conn.commit()
                return
            except (psycopg2.InterfaceError, psycopg2.OperationalError) as exc:
                last_exc = exc
                try:
                    self.conn.close()
                except Exception:
                    pass
                self.conn = self._connect()
            except Exception:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                raise
        raise last_exc

    # -------------------------
    # VECTOR SEARCH
    # -------------------------
    def search(self, query_vector: List[float], top_k: int = 5) -> List[Dict]:
        """
        Semantic search using pgvector cosine distance.

        Reconnects automatically if the connection has gone stale (Neon closes
        idle connections), retrying the query once.
        """
        vector_literal = self._to_vector_literal(query_vector)
        last_exc = None
        for attempt in range(2):
            try:
                self._ensure_conn()
                with self.conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, question, answer, text, metadata,
                               1 - (embedding <=> %s::vector) AS score
                        FROM faq_embeddings
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                        """,
                        (vector_literal, vector_literal, top_k)
                    )
                    rows = cur.fetchall()
                return [
                    {
                        "id": row[0],
                        "question": row[1],
                        "answer": row[2],
                        "text": row[3],
                        "metadata": row[4],
                        "score": row[5],
                    }
                    for row in rows
                ]
            except (psycopg2.InterfaceError, psycopg2.OperationalError) as exc:
                # Stale/broken connection — drop it, reconnect, and retry once.
                last_exc = exc
                try:
                    self.conn.close()
                except Exception:
                    pass
                self.conn = self._connect()
        raise last_exc

    def _to_vector_literal(self, values: List[float]) -> str:
        # pgvector text input format: [1.0,2.0,3.0]
        return "[" + ",".join(f"{float(v):.12g}" for v in values) + "]"
