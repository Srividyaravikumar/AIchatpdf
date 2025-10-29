// src/App.js
import React, { useEffect } from "react";
import Header from "./components/Header";
import LeftPane from "./components/LeftPane";
import ChatBox from "./components/ChatBox";
import "./App.css";

export default function App() {
  useEffect(() => {
    const base = process.env.REACT_APP_API_BASE;
    console.log("API BASE =", base);
    if (!base) {
      console.error("REACT_APP_API_BASE is missing. Set it in Vercel env vars and redeploy.");
      return;
    }
    fetch(`${base}/health`)
      .then((r) => r.json())
      .then((d) => console.log("Backend response:", d))
      .catch((e) => console.error("Backend fetch error:", e));
  }, []);

  return (
    <div className="App">
      <Header />
      <main className="content-row fullwidth">
        <section className="half left-plain">
          <div className="left-plain-inner">
            <LeftPane />
          </div>
        </section>

        <section className="half">
          <div className="box chat-card">
            <ChatBox />
          </div>
        </section>
      </main>
    </div>
  );
}
