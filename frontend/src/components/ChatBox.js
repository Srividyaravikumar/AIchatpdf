// src/components/ChatBox.jsx
import React, { useState } from "react";
const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";

export default function ChatBox() {
  const [messages, setMessages] = useState([
    { role: "ai", text: "Hello! Ask me anything about Germany’s Fiscal Code." }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim()) return;
    const question = input.trim();
    setMessages(prev => [...prev, { role: "user", text: question }]);
    setInput("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE.replace(/\/$/, "")}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question })
      });
      const data = await res.json();
      setMessages(prev => [
        ...prev,
        { role: "ai", text: data.answer || data.error || "Sorry, something went wrong." }
      ]);
    } catch {
      setMessages(prev => [...prev, { role: "ai", text: "Error: Unable to reach the backend." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat-container">
  <h2>Ask About German Tax Laws</h2>

  <div className="chat-window">
    {messages.map((m, i) => (
      <div
        key={i}
        className={m.role === "user" ? "message user" : "message ai"}
      >
        {m.text}
      </div>
    ))}
    {loading && <div className="message ai">Thinking...</div>}
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
  </div>
</div>

  );
}
