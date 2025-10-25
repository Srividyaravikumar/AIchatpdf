# backend/app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from pathlib import Path
import json, time, os
from chat_cf_rag import ask as rag_ask

app = Flask(__name__)

# Allowlist via env (comma-separated). Defaults cover local dev.
ALLOWED = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000"
).split(",")

CORS(app, resources={r"/*": {"origins": ALLOWED}})

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
