// src/components/ChatBox.jsx
import React, { useRef, useState } from "react";
import { API_BASE } from "../api";
const SUGGESTED_QUESTIONS = [
  "What is the purpose of the Fiscal Code?",
  "Who is considered a taxpayer under the Fiscal Code?",
  "What are the powers of the tax authorities?",
  "Explain international administrative assistance in tax matters.",
  "What deadlines and time limits are mentioned for tax procedures?",
  "What remedies/appeals are available against tax decisions?"
];

export default function ChatBox() {
  const [messages, setMessages] = useState([
    { role: "ai", text: "Hello! Ask me anything about Germany’s Fiscal Code." }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const abortRef = useRef(null);

  async function sendMessage() {
    if (!input.trim() || loading) return;

    const question = input.trim();
    setMessages((prev) => [
      ...prev,
      { role: "user", text: question },
      { role: "ai", text: "" }
    ]);
    setInput("");
    setLoading(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const url = `${API_BASE}/ask/stream`;
      const resp = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream"
        },
        body: JSON.stringify({ question }),
        signal: ctrl.signal
      });

      if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`);

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        let idx;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const raw = buffer.slice(0, idx).trim();
          buffer = buffer.slice(idx + 2);

          if (!raw) continue;
          if (raw.startsWith("event:")) continue;

          if (raw.startsWith("data:")) {
            const data = raw.slice(5).trim();

            if (data === "end") {
              // stop reading immediately
              try { await reader.cancel(); } catch {}
              break;
            }

            try {
              const parsed = JSON.parse(data);
              if (parsed?.delta) {
                setMessages((prev) => {
                  const out = [...prev];
                  const last = out[out.length - 1];
                  out[out.length - 1] = {
                    ...last,
                    text: (last.text || "") + parsed.delta
                  };
                  return out;
                });
              } else if (parsed?.error) {
                setMessages((prev) => [
                  ...prev,
                  { role: "ai", text: `Error: ${parsed.error}` }
                ]);
              }
            } catch {
              // Provider might send plain text lines
              setMessages((prev) => {
                const out = [...prev];
                const last = out[out.length - 1];
                out[out.length - 1] = {
                  ...last,
                  text: (last.text || "") + data
                };
                return out;
              });
            }
          }
        }
      }
    } catch (e) {
      setMessages((prev) => [...prev, { role: "ai", text: `Error: ${e.message}` }]);
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  }


  // src/components/ChatBox.js return snippet
// src/components/ChatBox.js (Snippet)
// src/components/ChatBox.js
return (
  <div className="chat-container">
    {/* This area will grow and scroll */}
    <div className="chat-window">
      {messages.map((m, i) => (
        <div key={i} className={`message ${m.role}`}>
          {m.text}
        </div>
      ))}
      {loading && <div className="message ai">Thinking...</div>}
    </div>
    <div className="suggestions">
  {SUGGESTED_QUESTIONS.map((q) => (
    <button
      key={q}
      type="button"
      className="suggestion-chip"
      onClick={() => {
        setInput(q);          // click-to-fill
        // OR send immediately:
        // setInput("");
        // sendMessage(q);
      }}
      disabled={loading}
      title="Click to use this question"
    >
      {q}
    </button>
  ))}
</div>

    {/* This area stays pinned at the bottom */}
    <div className="input-outer-wrapper">
      <div className="floating-input-bar">
        <span className="ai-sparkle">✦</span>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about the Fiscal Code..."
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
        />
        <button className="modern-send-btn" onClick={sendMessage}>
          {/* SVG Icon Code */}
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
        </button>
      </div>
    </div>
  </div>
);
}