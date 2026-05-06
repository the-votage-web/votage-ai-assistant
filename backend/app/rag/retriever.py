import psycopg2
from typing import List, Dict
import json


class PgVectorRetriever:
    def __init__(self, db_config):
        """
        Accepts either a DSN string or a dictionary of connection parameters.
        """
        if isinstance(db_config, str):
            self.conn = psycopg2.connect(db_config)
        else:
            self.conn = psycopg2.connect(**db_config)

    # -------------------------
    # STORE EMBEDDINGS
    # -------------------------
    def store_vectors(self, chunks: List[Dict]):
        """
        Inserts Q&A chunks into pgvector table
        """

        try:
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

    # -------------------------
    # VECTOR SEARCH
    # -------------------------
    def search(self, query_vector: List[float], top_k: int = 5) -> List[Dict]:
        """
        Semantic search using pgvector cosine distance
        """

        try:
            vector_literal = self._to_vector_literal(query_vector)
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
        except Exception:
            self.conn.rollback()
            raise

        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "question": row[1],
                "answer": row[2],
                "text": row[3],
                "metadata": row[4],
                "score": row[5],
            })

        return results

    def _to_vector_literal(self, values: List[float]) -> str:
        # pgvector text input format: [1.0,2.0,3.0]
        return "[" + ",".join(f"{float(v):.12g}" for v in values) + "]"
