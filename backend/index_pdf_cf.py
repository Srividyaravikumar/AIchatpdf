# index_pdf_cf.py
import os, re, hashlib, requests
from pathlib import Path
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.documents import Document


# add these imports near the top
import time
from typing import List
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ACC = os.environ["CLOUDFLARE_ACCOUNT_ID"]
TOK = os.environ["CLOUDFLARE_API_TOKEN"]
PDF = Path("Fiscal_Code_Germany_EN.pdf")
assert PDF.exists(), "Put your PDF next to this script."

EMBED_MODEL = "@cf/baai/bge-base-en-v1.5"
EMBED_URL = f"https://api.cloudflare.com/client/v4/accounts/{ACC}/ai/run/{EMBED_MODEL}"
HEADERS = {"Authorization": f"Bearer {TOK}", "Content-Type": "application/json"}

# build a resilient requests Session once
def _make_session():
    s = requests.Session()
    retry = Retry(
        total=5,                # up to 5 retries
        connect=5,
        read=5,
        backoff_factor=1.5,     # 1.5s, 3s, 4.5s, ...
        status_forcelist=[408, 429, 500, 502, 503, 504],
        allowed_methods=["POST"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=8)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

SESSION = _make_session()

def _post_embed_payload(payload, timeout=(10, 90)):
    # timeout = (connect, read) seconds
    r = SESSION.post(EMBED_URL, headers=HEADERS, json=payload, timeout=timeout)
    # Don't r.raise_for_status() immediately; handle non-200 gracefully
    if r.status_code >= 400:
        # Surface useful info
        try:
            detail = r.json()
        except Exception:
            detail = r.text[:500]
        raise RuntimeError(f"Embeddings HTTP {r.status_code}: {detail}")
    return r.json()

def _chunk(lst: List[str], n: int):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

# ---- REPLACE your cf_embed_batch with this ----
def cf_embed_batch(texts: List[str], batch_size: int = 16) -> List[List[float]]:
    out_vectors: List[List[float]] = []
    total = len(texts)
    for idx, batch in enumerate(_chunk(texts, batch_size), start=1):
        # try batch call first
        try:
            resp = _post_embed_payload({"text": batch})
            data = resp.get("result", {}).get("data")
            if not data or len(data) != len(batch):
                # if response malformed, fall back to per-item
                raise RuntimeError(f"Bad batch size from CF: got {len(data) if data else 0}, expected {len(batch)}")
            # data items are list vectors; sometimes dicts with 'embedding'
            for item in data:
                vec = item.get("embedding") if isinstance(item, dict) else item
                out_vectors.append(vec)
        except Exception as e:
            # fallback to per-item with small delay
            # (useful if the free pool is hot or request was too big)
            # print(f"Batch {idx} failed ({e}); falling back to per-item...")
            for t in batch:
                ok = False
                attempts = 0
                while not ok and attempts < 5:
                    attempts += 1
                    try:
                        resp = _post_embed_payload({"text": t})
                        data = resp.get("result", {}).get("data")
                        if not data:
                            raise RuntimeError(f"No data in per-item response: {resp}")
                        first = data[0]
                        vec = first.get("embedding") if isinstance(first, dict) else first
                        out_vectors.append(vec)
                        ok = True
                    except Exception as inner:
                        # simple backoff per item
                        time.sleep(1.5 * attempts)
                        if attempts == 5:
                            raise RuntimeError(f"Embedding failed after retries: {inner}") from inner
        # optional: tiny sleep to be nice to free tier
        time.sleep(0.25)
    if len(out_vectors) != total:
        raise RuntimeError(f"Got {len(out_vectors)} vectors, expected {total}")
    return out_vectors


# 1) Load PDF
docs = PyMuPDFLoader(str(PDF)).load()  # metadata has 'page'
for d in docs:
    # light clean
    d.page_content = re.sub(r"\n{3,}", "\n\n", d.page_content).strip()
    m = re.search(r"(§\s*\d+[a-zA-Z]*)\s+([^\n]+)?", d.page_content)
    if m:
        d.metadata["section"] = m.group(1)
        if m.lastindex and m.lastindex >= 2:
            d.metadata["title"] = (m.group(2) or "").strip()[:160]
    d.metadata["file"] = PDF.name
    d.metadata["hash"] = hashlib.md5(d.page_content.encode()).hexdigest()

# 2) Chunk (law-friendly)
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1200, chunk_overlap=150,
    separators=["\n§", "\n\n", "\n", ". ", "; ", ": ", " "],
)
chunks = splitter.split_documents(docs)

# 3) Embed via Cloudflare + store in Chroma (native client)
texts = [c.page_content for c in chunks]
embs = cf_embed_batch(texts)

# sanity checks
assert len(embs) == len(texts), f"emb count {len(embs)} != texts {len(texts)}"
assert all(isinstance(v, list) and len(v) == 768 for v in embs), "Embeddings must be 768-dim lists."

docs = [Document(page_content=texts[i], metadata=chunks[i].metadata) for i in range(len(texts))]
metadatas = [d.metadata for d in docs]
ids = [f"ao-{i:06d}" for i in range(len(texts))]

# ---> native ChromaDB upsert (no LangChain wrapper here)
import chromadb
client = chromadb.PersistentClient(path="../chroma_ao_en")
collection = client.get_or_create_collection(name="ao_en")

collection.upsert(
    ids=ids,
    documents=texts,
    embeddings=embs,
    metadatas=metadatas,
)

print(f"Indexed {len(texts)} chunks into chroma_ao_en/ao_en")
