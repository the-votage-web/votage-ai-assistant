"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type Msg = { role: "user" | "ai"; text: string };
type QuickAction = { label: string; message: string };
const DEFAULT_WELCOME_MESSAGE =
  "Hi 👋 I’m the church assistant.\n\nTap a quick action button below to get started (Check-in or FAQ).\n\n• To check in: send your phone number (e.g. 08012345678)\n• To ask: “What time is service?”";

const QUICK_ACTIONS: QuickAction[] = [
  { label: "Check-in", message: "I want to check in" },
  { label: "FAQ", message: "start faq session" },
];
const SERVICE_TYPE_ACTIONS: QuickAction[] = [
  { label: "Sunday Service", message: "sunday_service" },
  { label: "Connect", message: "connect" },
  { label: "Special Service", message: "special_service" },
];
const CONNECT_TYPE_ACTIONS: QuickAction[] = [
  { label: "Kabod", message: "KABOD CONNECT" },
  { label: "Newness", message: "NEWNESS CONNECT" },
  { label: "Ugbowo", message: "UGBOWO CONNECT" },
  { label: "Flourish", message: "FLOURISH CONNECT" },
  { label: "Gatekeepers", message: "GATEKEEPERS CONNECT" },
  { label: "Koinonia", message: "KOINONIA CONNECT" },
  { label: "Ekehuan", message: "EKEHUAN CONNECT" },
];

async function sendMessage(sessionId: string, message: string) {
  const base = process.env.NEXT_PUBLIC_API_BASE!;
  const res = await fetch(`${base}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  if (!res.ok) throw new Error("Request failed");
  return (await res.json()) as { reply: string };
}

function linkifyText(text: string) {
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  return text.split(urlRegex).map((part, i) => {
    if (/^https?:\/\/[^\s]+$/.test(part)) {
      return (
        <a
          key={`${part}-${i}`}
          href={part}
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: "#0057b8", textDecoration: "underline" }}
        >
          {part}
        </a>
      );
    }
    return part;
  });
}

function isServiceTypePrompt(text: string) {
  const normalized = text.toLowerCase();
  return (
    normalized.includes("choose a service type") ||
    (normalized.includes("service type") &&
      normalized.includes("sunday_service") &&
      normalized.includes("connect") &&
      normalized.includes("special_service"))
  );
}

function isWelcomePrompt(text: string) {
  const normalized = text.toLowerCase();
  return (
    normalized.includes("i’m the church assistant") ||
    normalized.includes("i'm the church assistant")
  ) && (
    normalized.includes("check-in") ||
    normalized.includes("to check in")
  ) && (
    normalized.includes("faq") ||
    normalized.includes("what time is service")
  );
}

function isConnectTypePrompt(text: string) {
  const normalized = text.toLowerCase();
  return (
    normalized.includes("choose your connect group") ||
    (normalized.includes("connect group") &&
      normalized.includes("kabod") &&
      normalized.includes("newness") &&
      normalized.includes("ugbowo") &&
      normalized.includes("flourish") &&
      normalized.includes("gatekeepers") &&
      (normalized.includes("koinonia") || normalized.includes("koinoinia")) &&
      normalized.includes("ekehuan"))
  );
}

export default function ChatWidget() {
  const sessionId = useMemo(() => crypto.randomUUID(), []);
  const [open, setOpen] = useState(true);
  const [busy, setBusy] = useState(false);
  const [input, setInput] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([
    {
      role: "ai",
      text: DEFAULT_WELCOME_MESSAGE,
    },
  ]);

  const endRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, open]);

  async function sendText(raw: string) {
    const text = raw.trim();
    if (!text || busy) return;

    setInput("");
    setMsgs((m) => [...m, { role: "user", text }]);
    setBusy(true);
    try {
      const { reply } = await sendMessage(sessionId, text);
      setMsgs((m) => [...m, { role: "ai", text: reply }]);
    } catch {
      setMsgs((m) => [
        ...m,
        { role: "ai", text: "Sorry — I couldn’t reach the server. Please try again." },
      ]);
    } finally {
      setBusy(false);
    }
  }

  async function onSend() {
    await sendText(input);
  }

  async function onEndSession() {
    if (busy) return;
    setInput("");
    setMsgs([{ role: "ai", text: DEFAULT_WELCOME_MESSAGE }]);
    try {
      await sendMessage(sessionId, "end session");
    } catch {
      // Ignore backend errors; UI has already been reset for a fresh start.
    }
  }

  return (
    <>
      <style>{`
        @keyframes typing-bounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
          40% { transform: translateY(-3px); opacity: 1; }
        }
      `}</style>

      {/* Floating button */}
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          position: "fixed",
          right: 18,
          bottom: 18,
          width: 54,
          height: 54,
          borderRadius: 999,
          border: "1px solid #ddd",
          background: "#fff",
          boxShadow: "0 10px 25px rgba(0,0,0,0.12)",
          cursor: "pointer",
          fontSize: 22,
        }}
        aria-label="Open chat"
      >
        💬
      </button>

      {/* Panel */}
      {open && (
        <div
          style={{
            position: "fixed",
            right: 18,
            bottom: 86,
            width: 360,
            maxWidth: "calc(100vw - 36px)",
            height: 520,
            maxHeight: "calc(100vh - 120px)",
            borderRadius: 16,
            border: "1px solid #ddd",
            background: "#fff",
            boxShadow: "0 18px 40px rgba(0,0,0,0.18)",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
          role="dialog"
          aria-label="Church assistant chat"
        >
          {/* Header */}
          <div
            style={{
              padding: "12px 12px",
              borderBottom: "1px solid #eee",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 10,
            }}
          >
            <div style={{ fontWeight: 700 }}>Votage Assistant</div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <button
                onClick={onEndSession}
                disabled={busy}
                style={{
                  border: "1px solid #d1d5db",
                  background: busy ? "#f3f4f6" : "#fff",
                  borderRadius: 10,
                  padding: "6px 10px",
                  cursor: busy ? "not-allowed" : "pointer",
                  fontSize: 12,
                }}
              >
                End session
              </button>
              <button
                onClick={() => setOpen(false)}
                style={{
                  border: "1px solid #eee",
                  background: "#fff",
                  borderRadius: 10,
                  padding: "6px 10px",
                  cursor: "pointer",
                }}
              >
                Close
              </button>
            </div>
          </div>

          {/* Messages */}
          <div style={{ padding: 12, overflowY: "auto", flex: 1 }}>
            {msgs.map((m, i) => (
              <div key={i}>
                <div
                  style={{
                    margin: "10px 0",
                    display: "flex",
                    justifyContent: m.role === "user" ? "flex-end" : "flex-start",
                  }}
                >
                  <div
                    style={{
                      padding: "10px 12px",
                      borderRadius: 12,
                      background: m.role === "user" ? "#E9F5FF" : "#F4F4F4",
                      maxWidth: "85%",
                      whiteSpace: "pre-wrap",
                      lineHeight: 1.35,
                    }}
                  >
                    {linkifyText(m.text)}
                  </div>
                </div>

                {m.role === "ai" && isWelcomePrompt(m.text) && (
                  <div
                    style={{
                      marginTop: 6,
                      marginBottom: 2,
                      display: "flex",
                      gap: 8,
                      flexWrap: "wrap",
                    }}
                  >
                    {QUICK_ACTIONS.map((action) => (
                      <button
                        key={action.label}
                        onClick={() => sendText(action.message)}
                        disabled={busy}
                        style={{
                          padding: "8px 10px",
                          borderRadius: 999,
                          border: "1px solid #ddd",
                          background: busy ? "#fafafa" : "#fff",
                          fontSize: 12,
                          cursor: busy ? "not-allowed" : "pointer",
                        }}
                      >
                        {action.label}
                      </button>
                    ))}
                  </div>
                )}

                {m.role === "ai" && isServiceTypePrompt(m.text) && (
                  <div
                    style={{
                      marginTop: 6,
                      marginBottom: 2,
                      display: "flex",
                      gap: 8,
                      flexWrap: "wrap",
                    }}
                  >
                    {SERVICE_TYPE_ACTIONS.map((action) => (
                      <button
                        key={action.label}
                        onClick={() => sendText(action.message)}
                        disabled={busy}
                        style={{
                          padding: "8px 10px",
                          borderRadius: 999,
                          border: "1px solid #d1d5db",
                          background: busy ? "#f3f4f6" : "#fff",
                          fontSize: 12,
                          cursor: busy ? "not-allowed" : "pointer",
                        }}
                      >
                        {action.label}
                      </button>
                    ))}
                  </div>
                )}

                {m.role === "ai" && isConnectTypePrompt(m.text) && (
                  <div
                    style={{
                      marginTop: 6,
                      marginBottom: 2,
                      display: "flex",
                      gap: 8,
                      flexWrap: "wrap",
                    }}
                  >
                    {CONNECT_TYPE_ACTIONS.map((action) => (
                      <button
                        key={action.label}
                        onClick={() => sendText(action.message)}
                        disabled={busy}
                        style={{
                          padding: "8px 10px",
                          borderRadius: 999,
                          border: "1px solid #d1d5db",
                          background: busy ? "#f3f4f6" : "#fff",
                          fontSize: 12,
                          cursor: busy ? "not-allowed" : "pointer",
                        }}
                      >
                        {action.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}

            {busy && (
              <div
                style={{
                  margin: "10px 0",
                  display: "flex",
                  justifyContent: "flex-start",
                }}
                aria-label="Assistant is typing"
              >
                <div
                  style={{
                    padding: "10px 12px",
                    borderRadius: 12,
                    background: "#F4F4F4",
                    display: "flex",
                    gap: 6,
                    alignItems: "center",
                  }}
                >
                  {[0, 1, 2].map((dot) => (
                    <span
                      key={dot}
                      style={{
                        width: 7,
                        height: 7,
                        borderRadius: "50%",
                        background: "#8f8f8f",
                        display: "inline-block",
                        animation: "typing-bounce 1.2s infinite ease-in-out",
                        animationDelay: `${dot * 0.15}s`,
                      }}
                    />
                  ))}
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {/* Input */}
          <div style={{ padding: 12, borderTop: "1px solid #eee" }}>
            <div style={{ display: "flex", gap: 8 }}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && onSend()}
              disabled={busy}
              placeholder={busy ? "Thinking…" : "Type a message…"}
              style={{
                flex: 1,
                padding: "10px 12px",
                borderRadius: 12,
                border: "1px solid #ddd",
                background: busy ? "#f3f4f6" : "#fff",
                outline: "none",
              }}
            />
            <button
              onClick={onSend}
              disabled={busy}
              style={{
                padding: "10px 14px",
                borderRadius: 12,
                border: "1px solid #111827",
                background: busy ? "#374151" : "#1f2937",
                color: "#fff",
                cursor: busy ? "not-allowed" : "pointer",
              }}
            >
              Send
            </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
