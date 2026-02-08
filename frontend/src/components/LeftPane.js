import React, { useEffect, useState } from "react";
import "./LeftPane.css";
import { API_BASE } from "../api";

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
        const data = await fetchJson(`${API_BASE}/facts`);
        const arr = Array.isArray(data)
          ? data
          : Array.isArray(data.facts)
          ? data.facts
          : [];
        setFacts(arr.map(String));
      } catch {
        try {
          const data = await fetchJson(FALLBACK_PUBLIC_URL);
          const arr = Array.isArray(data)
            ? data
            : Array.isArray(data.facts)
            ? data.facts
            : [];
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
      setIdx((i) => (i + 1) % facts.length);
    }, 30000);
    return () => clearInterval(id);
  }, [facts.length]);

  const current = facts.length ? facts[idx] : "";

  return (
    <div className="left-pane">

      <div className="bubble-below">
      Powered by Retrieval-Augmented Generation (RAG).
      </div>
      <div className="bubble-below">
      Understand Germany’s Fiscal Code (main tax law).
      </div>
      <div className="bubble-below">
      Document already in English, no translation needed.
      </div>
      <div className="bubble-below">
      Replies include exact legal citations from the official text.
      </div>
      <div className="bubble-below">
       Disclaimer: Not legal advice.
      </div>
      <h2 className="panel-title">Did You Know?</h2>

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
