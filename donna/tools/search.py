"""Document search and summarization tools using ChromaDB + Ollama."""

import os
import sys
import json
import httpx
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from knowledge.chroma_store import search_documents

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("DONNA_LLM_MODEL", "nemotron:120b")


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_cases",
            "description": "Search case documents for specific information. Use when the attorney asks about details in case files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for"},
                    "case_id": {"type": "string", "description": "Limit search to a specific case"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_document",
            "description": "Summarize a case document in 3 sentences. Use when attorney asks for a document summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Which document or what aspect to summarize"},
                    "case_id": {"type": "string", "description": "Case ID the document belongs to"},
                },
                "required": ["query"],
            },
        },
    },
]


def search_cases(query: str, case_id: str = None) -> dict:
    results = search_documents(query, case_id=case_id, n_results=5)

    if not results:
        return {"status": "no_results", "message": "No matching documents found."}

    return {
        "status": "found",
        "count": len(results),
        "results": results,
        "message": f"Found {len(results)} relevant passage(s).",
    }


def summarize_document(query: str, case_id: str = None) -> dict:
    results = search_documents(query, case_id=case_id, n_results=3)

    if not results:
        return {"status": "no_document", "message": "Could not find that document."}

    context = "\n\n".join([r["text"] for r in results])
    source = results[0].get("source", "unknown document")

    prompt = (
        f"Summarize the following document excerpt in exactly 3 sentences. "
        f"Focus on: incident location, parties involved, and key findings or outcome.\n\n"
        f"Document: {source}\n\n{context}"
    )

    try:
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=30.0,
        )
        resp.raise_for_status()
        summary = resp.json().get("response", "").strip()
    except Exception as e:
        summary = f"Summary unavailable: {e}. Raw excerpt: {context[:200]}..."

    return {
        "status": "summarized",
        "source": source,
        "summary": summary,
    }
