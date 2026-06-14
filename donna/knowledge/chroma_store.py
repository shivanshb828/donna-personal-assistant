"""ChromaDB vector store for Donna case document search."""

import os
import uuid
from pathlib import Path
from typing import Optional

import chromadb

CHROMA_HOST = os.environ.get("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", "8001"))
COLLECTION_NAME = "donna-cases"


def get_client() -> chromadb.HttpClient:
    return chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)


def get_collection():
    client = get_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def ingest_document(case_id: str, text: str, doc_type: str, filename: str, chunk_size: int = 512) -> list[str]:
    """Chunk text and add to ChromaDB. Returns list of chunk IDs."""
    collection = get_collection()
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunk_text = " ".join(words[i : i + chunk_size])
        if chunk_text.strip():
            chunks.append(chunk_text)

    if not chunks:
        return []

    ids = [f"{case_id}-{doc_type}-{i}" for i in range(len(chunks))]
    metadatas = [
        {"case_id": case_id, "doc_type": doc_type, "filename": filename, "chunk_index": i}
        for i in range(len(chunks))
    ]

    collection.add(documents=chunks, metadatas=metadatas, ids=ids)
    return ids


def ingest_file(case_id: str, file_path: str, doc_type: str) -> list[str]:
    """Read a text file and ingest into ChromaDB."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    text = path.read_text(encoding="utf-8", errors="replace")
    return ingest_document(case_id, text, doc_type, path.name)


def search_documents(query: str, case_id: Optional[str] = None, n_results: int = 5) -> list[dict]:
    """Search case documents. Optionally filter by case_id."""
    collection = get_collection()
    where_filter = {"case_id": case_id} if case_id else None

    results = collection.query(
        query_texts=[query],
        where=where_filter,
        n_results=n_results,
    )

    hits = []
    if results and results["documents"]:
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0
            hits.append({
                "text": doc,
                "source": meta.get("filename", "unknown"),
                "doc_type": meta.get("doc_type", "unknown"),
                "case_id": meta.get("case_id", ""),
                "relevance": round(1 - distance, 3),
            })

    return hits


if __name__ == "__main__":
    client = get_client()
    heartbeat = client.heartbeat()
    print(f"ChromaDB connected. Heartbeat: {heartbeat}")
    collection = get_collection()
    print(f"Collection '{COLLECTION_NAME}' ready. Count: {collection.count()}")
