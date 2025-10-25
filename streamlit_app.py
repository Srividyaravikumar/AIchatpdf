# streamlit_app.py
import re
import time
import json
from datetime import datetime
import streamlit as st

# Import your existing RAG function. It should accept a string and return a string.
from backend.chat_cf_rag import ask as rag_ask

st.set_page_config(
    page_title="Fiscal Code Chat",
    page_icon="📘",
    layout="wide",
    menu_items={
        "Get help": None,
        "Report a bug": None,
        "About": "Germany Fiscal Code (EN) • RAG over Cloudflare Workers AI + Vector DB"
    },
)

# ---------- Minimal CSS polish ----------
st.markdown(
    """
    <style>
      .app-title { font-size: 1.8rem; font-weight: 700; letter-spacing: .3px; }
      .subtitle { color: var(--text-color-secondary); margin-top: -6px; }
      .chat-bubble { background: rgba(0,0,0,0.03); border: 1px solid rgba(0,0,0,0.08);
                     border-radius: 12px; padding: 12px 14px; }
      .user-bubble { background: transparent; border: 1px dashed rgba(0,0,0,0.15); }
      .meta-row { font-size: 0.82rem; color: var(--text-color-secondary); }
      .pill { display:inline-block; padding: 2px 8px; border-radius: 999px;
              border: 1px solid rgba(0,0,0,0.1); margin-right: 6px; margin-bottom: 6px; }
      .code-like { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
                   font-size: 0.9rem; }
      .stTextInput input { border-radius: 10px; }
      .stButton>button { border-radius: 10px; height: 42px; }
      .sidebar-title { font-weight: 700; margin-top: 8px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Sidebar controls ----------
with st.sidebar:
    st.markdown("<div class='sidebar-title'>Settings</div>", unsafe_allow_html=True)
    st.caption("These mirror your retriever/reranker/LLM settings. Update your backend if you want them to actually change behavior.")
    k = st.slider("Retriever k", 6, 24, 12, step=2)
    top_k = st.slider("Reranker top_k", 2, 10, 4, step=1)
    temperature = st.slider("LLM temperature", 0.0, 1.0, 0.0, step=0.1)
    st.divider()
    st.markdown("<div class='sidebar-title'>Session</div>", unsafe_allow_html=True)
    if st.button("Clear chat history"):
        st.session_state.history = []
        st.session_state.last_latency_ms = None
        st.experimental_rerun()
    st.caption("History persists only while the app is running.")

# ---------- Helpers ----------
def extract_citations(text: str):
    """
    Parse citations like [§ 10, p.42] from the model answer.
    Returns a list of dicts with section and page.
    """
    pattern = r"\[§\s*([^\],]+)\s*,\s*p\.\s*([^\]]+)\]"
    cites = []
    for m in re.finditer(pattern, text):
        sec = m.group(1).strip()
        page = m.group(2).strip()
        cites.append({"section": sec, "page": page})
    return cites

def tokenish_count(s: str) -> int:
    # quick & dirty token estimate
    return max(1, int(len(s.split()) * 1.3))

# ---------- Session state ----------
if "history" not in st.session_state:
    st.session_state.history = []   # list of dicts: {"q":..., "a":..., "cites":[...], "latency_ms": ...}
if "last_latency_ms" not in st.session_state:
    st.session_state.last_latency_ms = None

# ---------- Header ----------
st.markdown("<div class='app-title'>Germany Fiscal Code Chatbot</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Ask precise questions about the Fiscal Code (EN). Answers always cite sections and pages.</div>", unsafe_allow_html=True)
st.divider()

# ---------- Layout: input on top, two columns below ----------
with st.container():
    col_inp1, col_inp2 = st.columns([4,1])
    with col_inp1:
        q = st.text_input("Your question", placeholder="e.g., How is residence defined for tax purposes?")
    with col_inp2:
        send = st.button("Ask", use_container_width=True, type="primary")

    if send and q.strip():
        started = time.perf_counter()
        try:
            ans = rag_ask(q.strip())  # your existing function (string -> string)
            latency_ms = int((time.perf_counter() - started) * 1000)
            cites = extract_citations(ans)
            st.session_state.history.append({
                "q": q.strip(),
                "a": ans,
                "cites": cites,
                "latency_ms": latency_ms,
                "k": k,
                "top_k": top_k,
                "temperature": temperature,
                "ts": datetime.utcnow().isoformat() + "Z",
            })
            st.session_state.last_latency_ms = latency_ms
        except Exception as e:
            st.error(f"Request failed: {e}")

# ---------- Two-column display ----------
left, right = st.columns([2.2, 1])

with left:
    st.subheader("Conversation")
    if not st.session_state.history:
        st.info("No messages yet. Ask something about the Fiscal Code to get started.")
    else:
        for turn in st.session_state.history[::-1]:  # newest first
            st.markdown(f"<div class='chat-bubble user-bubble'><b>You</b><br>{turn['q']}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='chat-bubble'><b>Bot</b><br>{turn['a']}</div>", unsafe_allow_html=True)
            meta = f"Latency: {turn['latency_ms']} ms · Settings: k={turn.get('k')}, top_k={turn.get('top_k')}, temp={turn.get('temperature')}"
            st.markdown(f"<div class='meta-row'>{meta}</div>", unsafe_allow_html=True)
            st.markdown("---")

with right:
    st.subheader("Sources")
    if st.session_state.history:
        cites = st.session_state.history[-1]["cites"]
        if cites:
            for c in cites:
                st.markdown(f"<span class='pill'>§ {c['section']} · p.{c['page']}</span>", unsafe_allow_html=True)
        else:
            st.caption("No citations parsed. The model should include [§ x, p.y] tags in the answer.")

    st.subheader("Utilities")
    # Copy latest answer
    if st.session_state.history:
        latest = st.session_state.history[-1]["a"]
        st.text_area("Copy answer", latest, height=120)
    # Download transcript
    transcript = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "turns": st.session_state.history
    }
    st.download_button(
        "Download transcript (.json)",
        data=json.dumps(transcript, ensure_ascii=False, indent=2),
        file_name="fiscal_code_chat_transcript.json",
        mime="application/json",
        use_container_width=True
    )
    # Token-ish stats
    total_user_tokens = sum(tokenish_count(t["q"]) for t in st.session_state.history)
    total_bot_tokens  = sum(tokenish_count(t["a"]) for t in st.session_state.history)
    st.caption(f"Approx tokens — user: {total_user_tokens}, bot: {total_bot_tokens}")

st.divider()
with st.expander("Notes"):
    st.write(
        "- This tool is a research aid. It is not legal advice.\n"
        "- Citations are parsed from patterns like `[§ 10, p.42]` embedded in the answer.\n"
        "- Retrieval settings in the sidebar are UI-only unless you wire them through to your backend."
    )
