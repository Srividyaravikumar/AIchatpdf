// src/App.js
import React, { useEffect } from "react";
import LeftPane from "./components/LeftPane";
import ChatBox from "./components/ChatBox";
import "./App.css";
import { API_BASE } from "./api";

export default function App() {
  return (
    <div className="App">
      {/* Sidebar Area */}
      <aside className="left-plain">
        <div className="sidebar-branding">
          <h1 className="logo-text">Chat Smarter.ai</h1>
          <div className="logo-subtext">An AI chat platform that explains German Fiscal code with grounded answers with exact § citations. </div>
        </div>
        <div className="left-plain-inner">
          <LeftPane />
        </div>
      </aside>
       
      {/* Main Chat Area */}
      <main className="chat-main-column">
        {/* We removed the Header component from here as requested */}
        <div className="hello"> Hello👋😊 </div>
        <section className="chat-content">
          <div className="box chat-card-wrapper">
            <ChatBox />
          </div>
        </section>

        <footer className="footer-status">
          <small>© {new Date().getFullYear()} Chat smarter.ai — Grounded Legal AI</small>
        </footer>
      </main>
    </div>
  );
}