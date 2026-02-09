from dotenv import load_dotenv
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from pathlib import Path
import json, time, os

from chat_cf_rag import ask as rag_ask, chat_stream as rag_stream

load_dotenv()  # Railway uses environment variables; .env is optional locally

app = Flask(__name__)

APP_ORIGIN = os.getenv("APP_ORIGIN", "https://chatsmarter.vercel.app")
ALLOWED = os.getenv(
    "ALLOWED_ORIGINS",
    f"http://localhost:3000,http://127.0.0.1:3000,{APP_ORIGIN}"
).split(",")

CORS(
    app,
    resources={r"/*": {"origins": ALLOWED}},
    supports_credentials=False,  # set True only if you use cookies
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=86400,
)

BASE_DIR = Path(__file__).resolve().parent
FACTS_GPT5_PATH = BASE_DIR / "facts_gpt5.json"

@app.get("/health")
def health():
    return jsonify({"ok": True, "facts_path": str(FACTS_GPT5_PATH), "exists": FACTS_GPT5_PATH.exists()})

@app.get("/facts")
def facts():
    if not FACTS_GPT5_PATH.exists():
        return jsonify({"error": "facts file missing", "path": str(FACTS_GPT5_PATH)}), 404
    with FACTS_GPT5_PATH.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    facts = data if isinstance(data, list) else data.get("facts", [])
    return jsonify({"facts": [str(x).strip() for x in facts], "updated_at": int(time.time())})

@app.post("/ask")
def ask():
    payload = request.get_json(silent=True) or {}
    q = (payload.get("question") or "").strip()
    if not q:
        return jsonify({"error": "missing 'question'"}), 400
    try:
        answer = rag_ask(q)
        return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"error": f"RAG failed: {str(e)}"}), 500

@app.post("/ask/stream")
def ask_stream():
    payload = request.get_json(silent=True) or {}
    q = (payload.get("question") or "").strip()
    if not q:
        return jsonify({"error": "missing 'question'"}), 400

    def generate():
        # First event so the client sees the stream is open
        yield b"event: ping\ndata: open\n\n"

        try:
            last_beat = time.time()

            for piece in rag_stream(q):
                now = time.time()

                # heartbeat every ~9s to keep proxies happy
                if now - last_beat > 9:
                    yield b"event: ping\ndata: hb\n\n"
                    last_beat = now

                if piece:
                    payload_bytes = json.dumps({"delta": piece}).encode("utf-8")
                    yield b"data: " + payload_bytes + b"\n\n"

            yield b"event: done\ndata: end\n\n"

        except Exception:
            # fallback to non-stream answer
            try:
                txt = rag_ask(q)
            except Exception as inner:
                err = json.dumps({"error": f"RAG failed: {inner}"}).encode("utf-8")
                yield b"event: error\ndata: " + err + b"\n\n"
                return

            for i in range(0, len(txt), 256):
                payload_bytes = json.dumps({"delta": txt[i:i+256]}).encode("utf-8")
                yield b"data: " + payload_bytes + b"\n\n"
                time.sleep(0.02)

            yield b"event: done\ndata: end\n\n"

    headers = {
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers=headers,
        direct_passthrough=True,
    )
