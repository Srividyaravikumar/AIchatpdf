import React, { useEffect, useState } from "react";
import "./LeftPane.css";

const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";
const FALLBACK_PUBLIC_URL = "/facts_gpt5.json";

export default function LeftPane() {
  const [facts, setFacts] = useState([]);
  const [idx, setIdx] = useState(0);
  const [ready, setReady] = useState(false);

  async function fetchJson(url) {
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    return res.json();
  }

  useEffect(() => {
    (async () => {
      try {
        const data = await fetchJson(`${API_BASE.replace(/\/$/, "")}/facts`);
        const arr = Array.isArray(data) ? data : Array.isArray(data.facts) ? data.facts : [];
        setFacts(arr.map(String));
      } catch {
        try {
          const data = await fetchJson(FALLBACK_PUBLIC_URL);
          const arr = Array.isArray(data) ? data : Array.isArray(data.facts) ? data.facts : [];
          setFacts(arr.map(String));
        } catch {
          setFacts([]);
        }
      } finally {
        setReady(true);
        setIdx(0);
      }
    })();
  }, []);

  // rotate every 30 s
  useEffect(() => {
    if (!facts.length) return;
    const id = setInterval(() => {
      setIdx(i => (i + 1) % facts.length);
    }, 30000);
    return () => clearInterval(id);
  }, [facts.length]);

  const current = facts.length ? facts[idx] : "";

  return (
    <div className="left-pane">
      {/* avatar + speech bubble */}
      <div className="hero">
  <div className="avatar">
    <div className="avatar-circle">
      <img src="/woman.png" alt="Avatar" className="avatar-img" />
    </div>
  </div>
  <div className="bubble">Hallo! 👋 </div>
</div>
      <div className="bubble-below">I’m your AI assistant powered by Retrieval-Augmented Generation (RAG).
I can help you explore and understand Germany’s Fiscal Code, the country’s main tax law.
No need to worry about translations, the original document was already published in English.
Just ask me any question about Germany’s tax rules, and I’ll reply with the exact legal citation straight from the official document. This is not a legal advice. </div>
      <h2 className="panel-title">Did You Know?</h2>

      {/* rotating single fact */}
      <div className="fact-rotator" aria-live="polite" aria-atomic="true">
        {!ready && <div className="placeholder">Loading…</div>}
        {ready && !current && <div className="placeholder">No facts available.</div>}
        {current && (
          <div key={idx} className="fact-card rotating">
            {current}
          </div>
        )}
      </div>
    </div>
  );
}
