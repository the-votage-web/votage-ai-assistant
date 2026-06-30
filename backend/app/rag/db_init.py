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

            # Chat logs: one row per question (question, answer, answered flag, score)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_logs (
                    id UUID PRIMARY KEY,
                    session_id TEXT,
                    question TEXT,
                    answer TEXT,
                    answered BOOLEAN,
                    top_score DOUBLE PRECISION,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
            """)

            # Admin-authored knowledge base entries (used live + exported to faq.md)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kb_entries (
                    id UUID PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'admin',
                    created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ,
                    exported_at TIMESTAMPTZ
                );
            """)

            # "Mark resolved" support on existing chat_logs
            cur.execute("""
                ALTER TABLE chat_logs
                ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ;
            """)

        self.conn.commit()
        print("✅ pgvector DB initialized")