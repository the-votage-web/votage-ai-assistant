"use client";

import { useCallback, useEffect, useState } from "react";
import styles from "./admin.module.css";

type Log = {
  id: string;
  question: string;
  answer: string;
  answered: boolean;
  top_score: number | null;
  resolved_at: string | null;
  created_at: string | null;
};

type KbEntry = { id: string; question: string; answer: string };
type Status = "all" | "answered" | "unanswered";

const KEY_STORAGE = "votage_admin_key";

export default function AdminPage() {
  const [adminKey, setAdminKey] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");

  const [tab, setTab] = useState<"logs" | "kb">("logs");
  const [status, setStatus] = useState<Status>("unanswered");
  const [search, setSearch] = useState("");
  const [logs, setLogs] = useState<Log[]>([]);
  const [kb, setKb] = useState<KbEntry[]>([]);
  const [editing, setEditing] = useState<{ question: string; answer: string; fromLogId?: string; kbId?: string } | null>(null);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    // Read the saved key once on mount. sessionStorage is client-only, so this
    // can't be a useState initializer without causing an SSR hydration mismatch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setAdminKey(sessionStorage.getItem(KEY_STORAGE));
  }, []);

  const authHeaders = useCallback(
    () => ({ "Content-Type": "application/json", "X-Admin-Key": adminKey ?? "" }),
    [adminKey]
  );

  const signOut = () => {
    sessionStorage.removeItem(KEY_STORAGE);
    setAdminKey(null);
    setPassword("");
  };

  async function onLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoginError("");
    const res = await fetch("/api/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (!res.ok) {
      setLoginError("Incorrect password. Please try again.");
      return;
    }
    sessionStorage.setItem(KEY_STORAGE, password);
    setAdminKey(password);
  }

  const [refreshKey, setRefreshKey] = useState(0);
  const refresh = () => setRefreshKey((k) => k + 1);

  useEffect(() => {
    if (!adminKey) return;
    let cancelled = false;
    void (async () => {
      if (tab === "logs") {
        const params = new URLSearchParams({ status, limit: "200" });
        if (search.trim()) params.set("q", search.trim());
        const res = await fetch(`/api/admin/logs?${params.toString()}`, { headers: authHeaders() });
        if (cancelled) return;
        if (res.status === 403) { signOut(); return; }
        if (res.ok) setLogs(await res.json());
      } else {
        const res = await fetch("/api/admin/kb", { headers: authHeaders() });
        if (cancelled) return;
        if (res.status === 403) { signOut(); return; }
        if (res.ok) setKb(await res.json());
      }
    })();
    return () => { cancelled = true; };
  }, [adminKey, tab, status, search, refreshKey, authHeaders]);

  async function saveEntry() {
    if (!editing) return;
    const isEdit = Boolean(editing.kbId);
    const url = isEdit ? `/api/admin/kb/${editing.kbId}` : "/api/admin/kb";
    const res = await fetch(url, {
      method: isEdit ? "PUT" : "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        question: editing.question,
        answer: editing.answer,
        from_log_id: editing.fromLogId ?? null,
      }),
    });
    if (res.status === 403) return signOut();
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setNotice(body.detail || "Could not save. Please try again.");
      return;
    }
    setEditing(null);
    setNotice("Saved to knowledge base. The bot can use it now.");
    refresh();
  }

  async function deleteEntry(id: string) {
    const res = await fetch(`/api/admin/kb/${id}`, { method: "DELETE", headers: authHeaders() });
    if (res.status === 403) return signOut();
    if (res.ok) refresh();
  }

  function exportFaq() {
    // Trigger a download through the proxy with the admin header.
    fetch("/api/admin/kb/export", { headers: authHeaders() })
      .then((r) => (r.ok ? r.blob() : Promise.reject()))
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "faq.md";
        a.click();
        URL.revokeObjectURL(a.href);
      })
      .catch(() => setNotice("Export failed. Please try again."));
  }

  if (!adminKey) {
    return (
      <main className={styles.loginWrap}>
        <form onSubmit={onLogin} className={styles.loginCard}>
          <h1 className={styles.title}>Admin Login</h1>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Admin password"
            className={styles.control}
            autoFocus
          />
          {loginError && <p className={styles.error}>{loginError}</p>}
          <button type="submit" className={styles.primaryBtn}>Sign in</button>
        </form>
      </main>
    );
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>Chat History & Knowledge</h1>
        <div className={styles.headerActions}>
          <button onClick={exportFaq} className={styles.secondaryBtn}>Export faq.md</button>
          <button onClick={signOut} className={styles.secondaryBtn}>Sign out</button>
        </div>
      </header>

      {notice && <div className={styles.notice} onClick={() => setNotice("")}>{notice}</div>}

      <nav className={styles.tabs}>
        <button className={tab === "logs" ? styles.tabActive : styles.tab} onClick={() => setTab("logs")}>Chat history</button>
        <button className={tab === "kb" ? styles.tabActive : styles.tab} onClick={() => setTab("kb")}>Knowledge base</button>
      </nav>

      {tab === "logs" && (
        <>
          <div className={styles.controls}>
            {(["unanswered", "answered", "all"] as Status[]).map((s) => (
              <button key={s} className={status === s ? styles.chipActive : styles.chip} onClick={() => setStatus(s)}>
                {s}
              </button>
            ))}
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search questions..."
              className={styles.search}
            />
          </div>
          <div className={styles.list}>
            {logs.map((log) => (
              <div key={log.id} className={styles.row}>
                <div className={styles.rowMain}>
                  <p className={styles.q}>{log.question}</p>
                  <p className={styles.a}>{log.answer}</p>
                  <div className={styles.meta}>
                    <span className={log.answered ? styles.badgeOk : styles.badgeGap}>
                      {log.answered ? "answered" : "unanswered"}
                    </span>
                    {log.resolved_at && <span className={styles.badgeResolved}>resolved</span>}
                    <span className={styles.date}>{log.created_at?.slice(0, 16).replace("T", " ")}</span>
                  </div>
                </div>
                <button
                  className={styles.primaryBtn}
                  onClick={() => setEditing({ question: log.question, answer: log.answered ? log.answer : "", fromLogId: log.id })}
                >
                  Answer / Edit
                </button>
              </div>
            ))}
            {logs.length === 0 && <p className={styles.empty}>No questions in this view yet.</p>}
          </div>
        </>
      )}

      {tab === "kb" && (
        <div className={styles.list}>
          <button className={styles.primaryBtn} onClick={() => setEditing({ question: "", answer: "" })}>
            + New entry
          </button>
          {kb.map((entry) => (
            <div key={entry.id} className={styles.row}>
              <div className={styles.rowMain}>
                <p className={styles.q}>{entry.question}</p>
                <p className={styles.a}>{entry.answer}</p>
              </div>
              <div className={styles.headerActions}>
                <button className={styles.secondaryBtn} onClick={() => setEditing({ question: entry.question, answer: entry.answer, kbId: entry.id })}>Edit</button>
                <button className={styles.dangerBtn} onClick={() => void deleteEntry(entry.id)}>Delete</button>
              </div>
            </div>
          ))}
          {kb.length === 0 && <p className={styles.empty}>No admin entries yet.</p>}
        </div>
      )}

      {editing && (
        <div className={styles.modalBackdrop} onClick={() => setEditing(null)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.title}>{editing.kbId ? "Edit entry" : "Write answer"}</h2>
            <label className={styles.label}>Question</label>
            <textarea
              className={styles.textarea}
              value={editing.question}
              onChange={(e) => setEditing({ ...editing, question: e.target.value })}
            />
            <label className={styles.label}>Answer</label>
            <textarea
              className={styles.textarea}
              value={editing.answer}
              onChange={(e) => setEditing({ ...editing, answer: e.target.value })}
              rows={6}
            />
            <div className={styles.headerActions}>
              <button className={styles.secondaryBtn} onClick={() => setEditing(null)}>Cancel</button>
              <button className={styles.primaryBtn} onClick={() => void saveEntry()}>Save to knowledge base</button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
