// src/App.js
import React from "react";
import Header from "./components/Header";
import LeftPane from "./components/LeftPane";
import ChatBox from "./components/ChatBox";
import "./App.css";

export default function App() {
  return (
    <div className="App">
      <Header />
      <main className="content-row fullwidth">
        {/* LEFT: plain (no card) */}
        <section className="half left-plain">
          {/* optional inner padding for spacing, but NO .box */}
          <div className="left-plain-inner">
            <LeftPane />
          </div>
        </section>

        {/* RIGHT: card */}
        <section className="half">
          <div className="box chat-card">
            <ChatBox />
          </div>
        </section>
      </main>
    </div>
  );
}
