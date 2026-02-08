// frontend/src/components/FactBox.jsx
import React, { useEffect, useState } from "react";
import "./FactBox.css";
import { API_BASE } from "../api";

const FALLBACK_PUBLIC_URL = "/facts_gpt5.json";

export default function FactBox() {
  const [facts, setFacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");

  async function fetchJson(url) {
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    return res.json();
  }

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        // Try backend first
        const data = await fetchJson(`${API_BASE}/facts`);
        const arr = Array.isArray(data)
          ? data
          : Array.isArray(data.facts)
          ? data.facts
          : [];

        if (!arr.length) throw new Error("Backend returned empty facts array.");

        setFacts(arr.map(String));
        setMsg(`Loaded ${arr.length} facts from backend.`);
      } catch {
        // Fallback to public file
        try {
          const data = await fetchJson(FALLBACK_PUBLIC_URL);
          const arr = Array.isArray(data)
            ? data
            : Array.isArray(data.facts)
            ? data.facts
            : [];

          if (!arr.length) throw new Error("Fallback file had no facts.");

          setFacts(arr.map(String));
          setMsg(`Loaded ${arr.length} facts from /public/facts_gpt5.json`);
        } catch {
          setFacts([]);
          setMsg("Failed to load facts from backend and fallback.");
        }
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="box factbox-wrapper">
      <div className="factbox">
        <h2 className="factbox-title">Did You Know?</h2>

        <div className="facts-scroll">
          {loading && <p>Loading facts…</p>}
          {!loading && facts.length === 0 && <p>No facts available.</p>}
          {!loading && facts.length > 0 && (
            <div className="facts-list">
              {facts.map((fact, i) => (
                <div key={i} className="fact-item">
                  {fact}
                </div>
              ))}
            </div>
          )}
        </div>

        <p className="factbox-msg">{msg}</p>
      </div>
    </div>
  );
}
