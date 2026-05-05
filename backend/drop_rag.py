import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")
engine = create_engine(db_url)

with engine.begin() as conn:
    conn.execute(text('DROP TABLE IF EXISTS rag_documents CASCADE'))
print("Dropped rag_documents table directly.")
