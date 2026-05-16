"""
Long-term memory: vector store of daily productivity summaries.
Uses ChromaDB for similarity search — lets the pipeline retrieve
"sessions similar to today" for richer few-shot context.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "daily_summaries"


def _get_client():
    import chromadb
    store_path = os.environ.get("VECTOR_STORE_PATH", "data/vectors")
    Path(store_path).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=store_path)


def _summary_to_document(summary: dict) -> tuple[str, dict]:
    """Convert a daily summary row to a (text, metadata) pair for embedding."""
    text = (
        f"Date: {summary['session_id']}. "
        f"Focus: {summary.get('focus_minutes', 0)}min. "
        f"Distracted: {summary.get('distracted_minutes', 0)}min. "
        f"Commits: {summary.get('commit_count', 0)}. "
        f"Goal completion: {summary.get('goal_completion_pct', 0):.0f}%. "
        f"Score: {summary.get('predicted_score', 0):.1f}/10. "
        f"Insights: {'; '.join(json.loads(summary.get('raw_insights') or '[]')[:2])}"
    )
    metadata = {k: v for k, v in summary.items() if k != "report_md" and v is not None}
    return text, metadata


async def upsert_summary(summary: dict) -> None:
    """Store or update a daily summary in the vector store."""
    try:
        def _upsert():
            client = _get_client()
            collection = client.get_or_create_collection(_COLLECTION_NAME)
            text, metadata = _summary_to_document(summary)
            collection.upsert(
                ids=[summary["session_id"]],
                documents=[text],
                metadatas=[metadata],
            )

        import asyncio
        await asyncio.to_thread(_upsert)
        logger.debug("[memory] upserted %s", summary["session_id"])
    except Exception:
        logger.exception("[memory] failed to upsert summary")


async def retrieve_similar_sessions(query_text: str, n: int = 3) -> list[dict]:
    """Find the N most similar past sessions to the given query text."""
    try:
        def _query():
            client = _get_client()
            collection = client.get_or_create_collection(_COLLECTION_NAME)
            results = collection.query(query_texts=[query_text], n_results=n)
            return results.get("metadatas", [[]])[0]

        import asyncio
        return await asyncio.to_thread(_query)
    except Exception:
        logger.exception("[memory] retrieve_similar_sessions failed")
        return []
