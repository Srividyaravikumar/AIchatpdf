// frontend/src/components/FactBox.jsx
import React, { useEffect, useState } from "react";
import "./FactBox.css";

const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";
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
      try {
        const data = await fetchJson(`${API_BASE.replace(/\/$/, "")}/facts`);
        const arr = Array.isArray(data) ? data :
                    Array.isArray(data.facts) ? data.facts : [];
        if (arr.length) {
          setFacts(arr.map(String));
          setMsg(`Loaded ${arr.length} facts from backend.`);
        } else {
          throw new Error("Backend returned empty facts array.");
        }
      } catch {
        try {
          const data = await fetchJson(FALLBACK_PUBLIC_URL);
          const arr = Array.isArray(data) ? data :
                      Array.isArray(data.facts) ? data.facts : [];
          if (arr.length) {
            setFacts(arr.map(String));
            setMsg(`Loaded ${arr.length} facts from /public/facts_gpt5.json`);
          } else {
            throw new Error("Fallback file had no facts.");
          }
        } catch {
          setFacts([]);
          setMsg("Failed to load facts from backend and fallback.");
        } finally {
          setLoading(false);
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
