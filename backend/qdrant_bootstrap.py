import os
import uuid
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from sentence_transformers import SentenceTransformer

from pathlib import Path
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

QURL = os.getenv("QDRANT_URL")
QKEY = os.getenv("QDRANT_API_KEY")
COLL = os.getenv("QDRANT_COLLECTION", "docs")

if not QURL or not QKEY:
    raise RuntimeError("Set QDRANT_URL and QDRANT_API_KEY in .env")

client = QdrantClient(url=QURL, api_key=QKEY, timeout=60)

# all-MiniLM-L6-v2 => 384-dim vectors
embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
DIM = 384

# Create collection if missing
try:
    client.get_collection(COLL)
    print(f"Collection {COLL} already exists")
except Exception:
    client.create_collection(
        collection_name=COLL,
        vectors_config=qm.VectorParams(size=DIM, distance=qm.Distance.COSINE),
    )
    print(f"Created collection {COLL} (dim={DIM})")

# Insert a few sample docs (use UUIDs so you never overwrite real data)
docs = [
    "Qdrant is a vector database used for semantic search.",
    "Retrieval-Augmented Generation combines search with LLMs.",
    "Flask serves a simple REST API for our RAG backend.",
]

vectors = embedder.encode(docs, normalize_embeddings=True)
points = [
    qm.PointStruct(
        id=str(uuid.uuid4()),
        vector=vectors[i].tolist(),
        payload={"text": docs[i], "source": "bootstrap"},
    )
    for i in range(len(docs))
]
client.upsert(collection_name=COLL, points=points)
print("Inserted sample points.")

# Run a query (use same embedding model + normalization)
query = "How do I combine search with a language model?"
qvec = embedder.encode(query, normalize_embeddings=True).tolist()
hits = client.query_points(collection_name=COLL, query=qvec, limit=3).points

print("\nTop matches:")
for h in hits:
    print(f"- score={h.score:.3f}  text={h.payload['text']}")

