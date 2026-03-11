import ChatWidget from "@/components/ChatWidget";
import Link from "next/link";

export default function Page() {
  return (
    <main style={{ padding: 24, fontFamily: "system-ui, sans-serif" }}>
      <h1>Welcome to Church</h1>
      <p>This page has the assistant widget in the bottom-right.</p>
      <p>
        <Link href="/register" style={{ color: "#0057b8", textDecoration: "none" }}>
          Go to Registration Form →
        </Link>
      </p>
      <ChatWidget />
    </main>
  );
}
