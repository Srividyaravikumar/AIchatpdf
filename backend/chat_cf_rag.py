# chat_cf_rag.py
from dotenv import load_dotenv
load_dotenv()
import os, requests, time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib import Path
from typing import List, Iterable
from langchain_chroma import Chroma

ACC = os.environ["CLOUDFLARE_ACCOUNT_ID"]
TOK = os.environ["CLOUDFLARE_API_TOKEN"]
H = {"Authorization": f"Bearer {TOK}", "Content-Type": "application/json"}

LLM = "@cf/meta/llama-3.1-8b-instruct"
EMBED = "@cf/baai/bge-base-en-v1.5"
RERANK = "@cf/baai/bge-reranker-base"

BASE_DIR = Path(__file__).resolve().parent
CHROMA_DIR = (BASE_DIR / "../chroma_ao_en").resolve()

def _session():
    s = requests.Session()
    retry = Retry(total=4, connect=4, read=4, backoff_factor=1.2,
                  status_forcelist=[408, 429, 500, 502, 503, 504],
                  allowed_methods=["POST"])
    adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=16)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

S = _session()

def _post(url, payload, timeout=(10, 240)):
    # bump read timeout to 240s to avoid mid-gen cutoffs
    r = S.post(url, headers=H, json=payload, timeout=timeout, stream=False)
    r.raise_for_status()
    return r.json()

LLM_URL   = f"https://api.cloudflare.com/client/v4/accounts/{ACC}/ai/run/{LLM}"
EMBED_URL = f"https://api.cloudflare.com/client/v4/accounts/{ACC}/ai/run/{EMBED}"
RERANK_URL= f"https://api.cloudflare.com/client/v4/accounts/{ACC}/ai/run/{RERANK}"

def cf_embed(q: str) -> List[float]:
    data = _post(EMBED_URL, {"text": q}).get("result", {}).get("data", [])
    first = data[0] if data else None
    vec = first.get("embedding") if isinstance(first, dict) else first
    if not vec or not isinstance(vec, list):
        raise RuntimeError("CF embed returned no vector")
    return vec

def cf_rerank(query: str, docs: List[str], top_k=4) -> List[int]:
    res = _post(RERANK_URL, {"query": query, "documents": docs})
    scores = res.get("result", {}).get("scores", [])
    if not scores or len(scores) != len(docs):
        return list(range(min(top_k, len(docs))))
    order = sorted(range(len(docs)), key=lambda i: scores[i], reverse=True)
    return order[:top_k]

def cf_chat(system: str, user: str) -> str:
    # non-stream path
    res = _post(LLM_URL, {
        "messages":[{"role":"system","content":system},{"role":"user","content":user}],
        "temperature":0,
    }, timeout=(10, 240))
    out = res.get("result", {}).get("response")
    if not out:
        raise RuntimeError(f"CF chat returned no response: {res}")
    return out

def cf_chat_stream(system: str, user: str) -> Iterable[str]:
    """
    Try provider streaming; if not supported, fallback to one-shot.
    We still yield small pieces so SSE stays lively.
    """
    try:
        # If Cloudflare supports streaming for your model, flip the payload accordingly.
        # Some deployments accept {"stream": True}. If not, we fallback.
        with S.post(LLM_URL,
                    headers=H,
                    json={"messages":[{"role":"system","content":system},{"role":"user","content":user}],
                          "temperature":0,
                          "stream": True},
                    timeout=(10, 240),
                    stream=True) as r:
            r.raise_for_status()
            buf = []
            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                # Different providers format events differently; try to extract token-ish text.
                # If line has JSON with "response" or "delta", handle both:
                if line.startswith("data:"):
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    buf.append(payload)
                    # Emit in small slices to the caller
                    if len("".join(buf)) >= 128:
                        chunk = "".join(buf)
                        buf = []
                        yield chunk
            # flush remainder
            if buf:
                yield "".join(buf)
            return
    except Exception:
        # fall back to one-shot
        txt = cf_chat(system, user)
        for i in range(0, len(txt), 200):
            yield txt[i:i+200]

db = Chroma(collection_name="ao_en", persist_directory=str(CHROMA_DIR))

SYSTEM = ("You answer ONLY using the provided context from Germany’s Fiscal Code (English). "
          "Be concise. ALWAYS cite like [§ {section}, p.{page}]. If not in context, say so. "
          "This is not legal advice.")

def _fmt_page(md):
    p = md.get("page")
    try:
        return int(p) + 1
    except Exception:
        return "—"

def ask(q: str) -> str:
    q_vec = cf_embed(q)
    candidates = db.similarity_search_by_vector(q_vec, k=12)
    texts = [d.page_content for d in candidates]
    try:
        order = cf_rerank(q, texts, top_k=4)
        chosen = [candidates[i] for i in order]
    except Exception:
        chosen = candidates[:4]

    context = "\n\n".join(
        f"[§ {d.metadata.get('section','—')}, p.{_fmt_page(d.metadata)}] {d.page_content}"
        for d in chosen
    )
    prompt = f"Question: {q}\n\nContext:\n{context}\n\nAnswer (with citations):"
    return cf_chat(SYSTEM, prompt)

def chat_stream(q: str) -> Iterable[str]:
    # same retrieval, but use streaming chat
    q_vec = cf_embed(q)
    candidates = db.similarity_search_by_vector(q_vec, k=12)
    texts = [d.page_content for d in candidates]
    try:
        order = cf_rerank(q, texts, top_k=4)
        chosen = [candidates[i] for i in order]
    except Exception:
        chosen = candidates[:4]

    context = "\n\n".join(
        f"[§ {d.metadata.get('section','—')}, p.{_fmt_page(d.metadata)}] {d.page_content}"
        for d in chosen
    )
    prompt = f"Question: {q}\n\nContext:\n{context}\n\nAnswer (with citations):"
    for chunk in cf_chat_stream(SYSTEM, prompt):
        yield chunk
