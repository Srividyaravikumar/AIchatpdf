// src/components/ChatBox.jsx
import React, { useRef, useState } from "react";
const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";

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
    setMessages(prev => [...prev, { role: "user", text: question }, { role: "ai", text: "" }]);
    setInput("");
    setLoading(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const url = `${API_BASE.replace(/\/$/, "")}/ask/stream`;
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
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
              break;
            }
            try {
              const parsed = JSON.parse(data);
              if (parsed?.delta) {
                setMessages(prev => {
                  const out = [...prev];
                  out[out.length - 1] = { ...out[out.length - 1], text: (out[out.length - 1].text || "") + parsed.delta };
                  return out;
                });
              } else if (parsed?.error) {
                setMessages(prev => [...prev, { role: "ai", text: `Error: ${parsed.error}` }]);
              }
            } catch {
              // provider might send plain text lines
              setMessages(prev => {
                const out = [...prev];
                out[out.length - 1] = { ...out[out.length - 1], text: (out[out.length - 1].text || "") + data };
                return out;
              });
            }
          }
        }
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: "ai", text: `Error: ${e.message}` }]);
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  }

  function stopStreaming() {
    if (abortRef.current) abortRef.current.abort();
  }

  return (
    <div className="chat-container">
      <h2>Ask About German Tax Laws</h2>

      <div className="chat-window">
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "message user" : "message ai"}>
            {m.text}
          </div>
        ))}
        {loading && <div className="message ai">Thinking… (you can stop)</div>}
      </div>

      <div className="input-row">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask a question about the Fiscal Code..."
          onKeyDown={e => { if (e.key === "Enter") sendMessage(); }}
        />
        <button onClick={sendMessage} disabled={loading}>Send</button>
        <button onClick={stopStreaming} disabled={!loading}>Stop</button>
      </div>
    </div>
  );
}
