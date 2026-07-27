"use client";

import { useRouter } from "next/navigation";
import { MouseEvent, useEffect, useMemo, useRef, useState } from "react";
import { reportIssue } from "@/lib/reportIssue";

type Msg = { role: "user" | "ai"; text: string };
type QuickAction = { label: string; message: string };
const DEFAULT_WELCOME_MESSAGE =
  "Hi 👋 I’m the church assistant. I'm here to help with any questions you have about our services and events.\n\nYou can ask me things like: “What time is service?” or “How do I join a connect group?”";

const QUICK_ACTIONS: QuickAction[] = [
  { label: "Start FAQ Session", message: "start faq session" },
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

function normalizeMissingMemberReply(text: string) {
  const markdownRegisterUrl = text.match(/\((https?:\/\/[^\s)]+\/register(?:\?[^\s)]*)?)\)/)?.[1];
  const plainRegisterUrl = text.match(/https?:\/\/[^\s)]+\/register(?:\?[^\s)]*)?/)?.[0];
  const registerUrl = markdownRegisterUrl || plainRegisterUrl;
  const looksLikeMissingMember =
    /recognize that phone number|couldn't find a member record|register here first/i.test(text) ||
    (Boolean(registerUrl) &&
      text
        .replace(/\[[^\]]*\]\((https?:\/\/[^\s)]+)\)/g, "$1")
        .trim() === registerUrl);

  if (!registerUrl || !looksLikeMissingMember) {
    return text;
  }

  return `👋 I don’t recognize that phone number yet.\nPlease register here first: ${registerUrl}`;
}


function isInternalUrl(url: string) {
  if (typeof window === "undefined") return false;
  try {
    const resolved = new URL(url, window.location.origin);
    return resolved.origin === window.location.origin;
  } catch {
    return false;
  }
}

function toAppPath(url: string) {
  if (typeof window === "undefined") return url;
  const resolved = new URL(url, window.location.origin);
  return `${resolved.pathname}${resolved.search}${resolved.hash}`;
}

function linkifyText(
  text: string,
  onInternalNavigate: (url: string, event: MouseEvent<HTMLAnchorElement>) => void
) {
  const regex = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|(https?:\/\/[^\s]+)/g;
  const result: Array<string | React.ReactElement> = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    const [fullMatch, markdownLabel, markdownUrl, rawUrl] = match;
    const start = match.index;

    if (start > lastIndex) {
      result.push(text.slice(lastIndex, start));
    }

    const href = markdownUrl || rawUrl;
    const label = markdownLabel || href;
    const internal = isInternalUrl(href);

    result.push(
      <a
        key={`${href}-${start}`}
        href={href}
        target={internal ? undefined : "_blank"}
        rel={internal ? undefined : "noopener noreferrer"}
        onClick={(event) => {
          if (internal) onInternalNavigate(href, event);
        }}
        style={{ color: "#0057b8", textDecoration: "underline" }}
      >
        {label}
      </a>
    );

    lastIndex = start + fullMatch.length;
  }

  if (lastIndex < text.length) {
    result.push(text.slice(lastIndex));
  }

  return result.length > 0 ? result : [text];
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
    normalized.includes("faq") ||
    normalized.includes("what time is service") ||
    normalized.includes("registration page")
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


export default function ChatWidget({
  apiUrl = "/api/chat",
  welcomeMessage = DEFAULT_WELCOME_MESSAGE,
  containerStyle = {},
}: {
  apiUrl?: string;
  welcomeMessage?: string;
  containerStyle?: React.CSSProperties;
}) {
  const router = useRouter();
  const sessionId = useMemo(() => crypto.randomUUID(), []);
  const [busy, setBusy] = useState(false);
  const [input, setInput] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([
    {
      role: "ai",
      text: welcomeMessage,
    },
  ]);

  const endRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs]);

  function handleInternalNavigate(url: string, event: MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    router.push(toAppPath(url));
  }

  async function sendText(raw: string) {
    const text = raw.trim();
    if (!text || busy) return;

    setInput("");
    setMsgs((m) => [...m, { role: "user", text }]);

    setBusy(true);
    try {
      const base = process.env.NEXT_PUBLIC_API_BASE || "";
      const url = base ? `${base}${apiUrl}` : apiUrl;
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: text }),
      });
      if (!res.ok) {
        if (res.status === 503) {
          throw new Error("SERVICE_BUSY");
        }
        throw new Error("Request failed");
      }
      const { reply } = (await res.json()) as { reply: string };
      const normalizedReply =
        apiUrl.includes("checkin") ? normalizeMissingMemberReply(reply) : reply;
      setMsgs((m) => [...m, { role: "ai", text: normalizedReply }]);
    } catch (err) {
      const busyMessage =
        "I’m receiving too many requests right now. Please try again in a minute.";
      const shown =
        err instanceof Error && err.message === "SERVICE_BUSY"
          ? busyMessage
          : "Sorry — I couldn’t reach the server. Please try again.";
      setMsgs((m) => [...m, { role: "ai", text: shown }]);
      if (apiUrl.includes("checkin")) {
        void reportIssue({
          kind: "checkin",
          message: shown,
          httpStatus: err instanceof Error && err.message === "SERVICE_BUSY" ? 503 : undefined,
          sessionId,
          details: { typed: text },
        });
      }
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
    setMsgs([{ role: "ai", text: welcomeMessage }]);
    try {
      const base = process.env.NEXT_PUBLIC_API_BASE || "";
      const url = base ? `${base}${apiUrl}` : apiUrl;
      await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: "end session" }),
      });
    } catch {
      // Ignore backend errors; UI has already been reset for a fresh start.
    }
  }

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(180deg, #f7fafc 0%, #edf2f7 100%)",
        padding: 10,
        boxSizing: "border-box",
        ...containerStyle,
      }}
    >
      <style>{`
        @keyframes typing-bounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
          40% { transform: translateY(-3px); opacity: 1; }
        }
      `}</style>

      <div
        style={{
          width: "min(980px, 100%)",
          height: "min(820px, 100%)",
          maxHeight: "100%",
          borderRadius: 16,
          border: "1px solid #e2e8f0",
          background: "#fff",
          boxShadow: "0 22px 60px rgba(15,23,42,0.12)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
        role="main"
        aria-label="Church assistant"
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
                    {linkifyText(m.text, handleInternalNavigate)}
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
    </div>
  );
}
