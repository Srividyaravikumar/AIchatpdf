# backend/app.py
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from pathlib import Path
import json, time, os
from chat_cf_rag import ask as rag_ask, chat_stream as rag_stream  # new import

app = Flask(__name__)

# Allow Vercel + local dev
APP_ORIGIN = os.getenv("APP_ORIGIN", "https://chatsmarter.vercel.app")
ALLOWED = os.getenv(
    "ALLOWED_ORIGINS",
    f"http://localhost:3000,http://127.0.0.1:3000,{APP_ORIGIN}"
).split(",")

CORS(
    app,
    resources={r"/*": {"origins": ALLOWED}},
    supports_credentials=True,
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=86400,
)

BASE_DIR = Path(__file__).resolve().parent
FACTS_GPT5_PATH = BASE_DIR / "facts_gpt5.json"

# Preflight: reply fast so browser proceeds to real request
@app.route("/<path:_any>", methods=["OPTIONS"])
def options_ok(_any):
    return ("", 204)

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
        # Open the pipe fast so edges don’t think we’re idle
        yield "event: ping\ndata: open\n\n"

        # Try model streaming first; fallback to non-stream + chunking
        try:
            # rag_stream should yield small string chunks
            last_beat = time.time()
            for piece in rag_stream(q):
                # heartbeat every ~9s to keep Cloudflare happy
                now = time.time()
                if now - last_beat > 9:
                    yield "event: ping\ndata: hb\n\n"
                    last_beat = now
                if piece:
                    payload = json.dumps({"delta": piece})
                    yield f"data: {payload}\n\n"
            yield "event: done\ndata: end\n\n"
        except Exception as e:
            # fallback: one-shot call, then chunk it so the UI still streams
            try:
                txt = rag_ask(q)
            except Exception as inner:
                err = f"RAG failed: {inner}"
                yield f"event: error\ndata: {json.dumps({'error': err})}\n\n"
                return
            for i in range(0, len(txt), 256):
                yield f"data: {json.dumps({'delta': txt[i:i+256]})}\n\n"
                time.sleep(0.02)
            yield "event: done\ndata: end\n\n"

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return Response(stream_with_context(generate()), headers=headers)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))  # Render sets PORT
    app.run(host="0.0.0.0", port=port, debug=True)
