"""
Index one or more PDFs into Qdrant for RAG retrieval.

- Extracts text from PDFs (PyMuPDF preferred, pypdf fallback)
- Chunks with overlap (paragraph-aware)
- Embeds using sentence-transformers/all-MiniLM-L6-v2 (384-dim)
- Upserts into Qdrant with payload["text"] (compatible with chat_cf_rag.py)

Usage examples:
  python -m backend.index_pdf_qdrant --pdf /path/to/file.pdf
  python -m backend.index_pdf_qdrant --dir /path/to/pdfs
  python -m backend.index_pdf_qdrant --pdf file.pdf --collection docs --recreate --i-understand
"""

import os
import re
import argparse
import hashlib
from pathlib import Path
from typing import List, Dict, Iterable, Tuple, Optional
import uuid
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from sentence_transformers import SentenceTransformer

from pathlib import Path
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

# ----------------------------
# PDF reading
# ----------------------------
def _read_pdf_text(path: Path) -> List[Tuple[int, str]]:
    """Return list of (page_number_1_based, page_text)."""
    # Try PyMuPDF (fitz)
    try:
        import fitz  # PyMuPDF
        pages: List[Tuple[int, str]] = []
        with fitz.open(str(path)) as doc:
            for i in range(doc.page_count):
                text = doc.load_page(i).get_text("text") or ""
                pages.append((i + 1, text))
        return pages
    except Exception:
        pass

    # Fallback: pypdf
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        pages: List[Tuple[int, str]] = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages.append((i + 1, text))
        return pages
    except Exception as e:
        raise RuntimeError(
            "Could not read PDF. Install PyMuPDF (pymupdf) or pypdf.\n"
            f"Error: {e}"
        )


# ----------------------------
# Text cleaning + chunking
# ----------------------------
def _clean_text(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _chunk_paragraph_aware(text: str, chunk_size: int, overlap: int) -> List[str]:
    """
    Paragraph-aware chunking:
    - split into paragraphs
    - pack paragraphs into chunks up to chunk_size
    - apply overlap by reusing trailing text
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be < chunk_size")

    text = _clean_text(text)
    if not text:
        return []

    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paras:
        return []

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    def flush():
        nonlocal current, current_len
        if current:
            chunk = "\n\n".join(current).strip()
            if chunk:
                chunks.append(chunk)
        current = []
        current_len = 0

    for p in paras:
        p_len = len(p)
        # If paragraph alone is bigger than chunk_size, fall back to windowing it.
        if p_len > chunk_size:
            flush()
            chunks.extend(_chunk_window(p, chunk_size, overlap))
            continue

        # If it fits in current chunk, add it
        add_len = p_len + (2 if current else 0)  # account for \n\n between paras
        if current_len + add_len <= chunk_size:
            current.append(p)
            current_len += add_len
        else:
            flush()
            current.append(p)
            current_len = p_len

    flush()

    # Now apply overlap between chunks (simple trailing-char reuse)
    if overlap > 0 and len(chunks) > 1:
        overlapped: List[str] = [chunks[0]]
        for i in range(1, len(chunks)):
            prev = overlapped[-1]
            tail = prev[-overlap:] if len(prev) > overlap else prev
            merged = (tail + "\n" + chunks[i]).strip()
            # Keep within a reasonable bound (avoid ballooning)
            if len(merged) > chunk_size + overlap:
                merged = merged[: chunk_size + overlap].strip()
            overlapped.append(merged)
        chunks = overlapped

    return chunks


def _chunk_window(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Character windowing with overlap (fallback)."""
    text = _clean_text(text)
    if not text:
        return []

    chunks: List[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == n:
            break
        start = max(0, end - overlap)
    return chunks


# ----------------------------
# Qdrant helpers
# ----------------------------
def _require_env(name: str, default: Optional[str] = None) -> str:
    v = os.getenv(name, default)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


def _ensure_collection(client: QdrantClient, collection: str, vector_size: int, recreate: bool) -> None:
    """
    Create collection if missing. Optionally recreate.
    Uses COSINE distance because we normalize embeddings.
    Also checks vector size (best-effort) when collection exists.
    """
    exists = False
    info = None
    try:
        info = client.get_collection(collection)
        exists = True
    except Exception:
        exists = False

    if recreate and exists:
        client.delete_collection(collection)
        exists = False
        info = None

    if not exists:
        client.create_collection(
            collection_name=collection,
            vectors_config=qm.VectorParams(size=vector_size, distance=qm.Distance.COSINE),
        )
        return

    # Best-effort size check (field path can vary by qdrant-client versions)
    try:
        existing_size = info.config.params.vectors.size  # type: ignore[attr-defined]
        if int(existing_size) != int(vector_size):
            raise RuntimeError(
                f"Collection '{collection}' vector size is {existing_size}, expected {vector_size}. "
                f"Use --recreate --i-understand to rebuild."
            )
    except Exception:
        # If the SDK structure differs, skip size check rather than crashing.
        pass


def _iter_pdfs(pdf: Optional[Path], directory: Optional[Path]) -> Iterable[Path]:
    if pdf:
        yield pdf
        return
    if directory:
        for p in sorted(directory.rglob("*.pdf")):
            yield p
        return
    raise ValueError("Provide either --pdf or --dir")




def _stable_point_id(pdf_path: str, page_no: int, chunk_idx: int) -> str:
    # Deterministic UUID derived from a stable string
    name = f"{pdf_path}|{page_no}|{chunk_idx}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, name))



# ----------------------------
# Main
# ----------------------------
def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=str, default=None, help="Path to a single PDF")
    parser.add_argument("--dir", type=str, default=None, help="Path to a directory of PDFs (recursive)")
    parser.add_argument("--collection", type=str, default=os.getenv("QDRANT_COLLECTION", "docs"))
    parser.add_argument("--chunk-size", type=int, default=1200)
    parser.add_argument("--overlap", type=int, default=200)
    parser.add_argument("--recreate", action="store_true", help="Drop & recreate collection (DANGEROUS)")
    parser.add_argument("--i-understand", action="store_true", help="Required with --recreate")
    parser.add_argument("--batch", type=int, default=64, help="Upsert batch size")
    args = parser.parse_args()

    if args.recreate and not args.i_understand:
        raise RuntimeError("Refusing to --recreate without --i-understand")

    pdf_path = Path(args.pdf).resolve() if args.pdf else None
    dir_path = Path(args.dir).resolve() if args.dir else None

    qurl = _require_env("QDRANT_URL")
    qkey = _require_env("QDRANT_API_KEY")
    collection = args.collection

    client = QdrantClient(url=qurl, api_key=qkey, timeout=60)
    embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    VECTOR_SIZE = 384
    _ensure_collection(client, collection, VECTOR_SIZE, recreate=args.recreate)

    total_points = 0

    for pdf_file in _iter_pdfs(pdf_path, dir_path):
        if not pdf_file.exists():
            raise FileNotFoundError(str(pdf_file))

        pages = _read_pdf_text(pdf_file)

        points: List[qm.PointStruct] = []
        for page_no, page_text in pages:
            page_text = _clean_text(page_text)
            if not page_text:
                continue

            chunks = _chunk_paragraph_aware(page_text, chunk_size=args.chunk_size, overlap=args.overlap)
            if not chunks:
                continue

            vectors = embedder.encode(chunks, normalize_embeddings=True)

            for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
                payload: Dict[str, object] = {
                    "text": chunk,  # IMPORTANT: chat_cf_rag.py expects payload["text"]
                    "source": pdf_file.name,
                    "path": str(pdf_file),
                    "page": page_no,
                    "chunk": idx,
                    "chunk_chars": len(chunk),
                }
                points.append(
                    qm.PointStruct(
                        id=_stable_point_id(str(pdf_file), page_no, idx),

                        vector=vec.tolist(),
                        payload=payload,
                    )
                )

                if len(points) >= args.batch:
                    client.upsert(collection_name=collection, points=points)
                    total_points += len(points)
                    points = []

        if points:
            client.upsert(collection_name=collection, points=points)
            total_points += len(points)

        print(f"Indexed: {pdf_file.name}")

    print(f"Done. Upserted {total_points} chunks into collection '{collection}'.")


if __name__ == "__main__":
    main()
