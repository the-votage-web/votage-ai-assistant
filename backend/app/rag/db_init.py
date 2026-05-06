import psycopg2


class DBInitializer:
    def __init__(self, database_url: str):
        self.conn = psycopg2.connect(database_url)

    def setup(self):
        with self.conn.cursor() as cur:

            # Enable pgvector
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

            # Create table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS faq_embeddings (
                    id TEXT PRIMARY KEY,
                    question TEXT,
                    answer TEXT,
                    text TEXT,
                    embedding vector(1536),
                    metadata JSONB
                );
            """)

            # Index for performance
            cur.execute("""
                CREATE INDEX IF NOT EXISTS faq_embedding_idx
                ON faq_embeddings
                USING hnsw (embedding vector_cosine_ops);
            """)

        self.conn.commit()
        print("✅ pgvector DB initialized")