import unittest
import psycopg2

from app.rag.retriever import PgVectorRetriever


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, *a, **k):
        # Simulate Neon dropping an idle connection on first use.
        if self.conn.fail_once and not self.conn.failed:
            self.conn.failed = True
            raise psycopg2.InterfaceError("connection already closed")

    def fetchall(self):
        return []


class FakeConn:
    def __init__(self, fail_once=False):
        self.fail_once = fail_once
        self.failed = False
        self.closed = 0
        self.committed = False
        self.deleted = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        self.closed = 1


def _make_retriever(first_conn, reconnects):
    r = object.__new__(PgVectorRetriever)
    r.db_config = "dsn"
    r.conn = first_conn
    r._connect = lambda: reconnects.pop(0)
    return r


class TestWriteReconnect(unittest.TestCase):
    def test_upsert_retries_on_stale_connection(self):
        good = FakeConn(fail_once=False)
        r = _make_retriever(FakeConn(fail_once=True), [good])
        r.upsert_vector({
            "id": "admin:1", "question": "q", "answer": "a", "text": "Q: q\nA: a",
            "embedding": [0.1, 0.2, 0.3], "metadata": {},
        })
        self.assertTrue(good.committed)  # succeeded after reconnect

    def test_delete_retries_on_stale_connection(self):
        good = FakeConn(fail_once=False)
        r = _make_retriever(FakeConn(fail_once=True), [good])
        r.delete_vector("admin:1")
        self.assertTrue(good.committed)


if __name__ == "__main__":
    unittest.main()
