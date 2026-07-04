import asyncio
import re
from dataclasses import dataclass
from typing import Optional
import structlog
from rank_bm25 import BM25Okapi
from app.services.vector_store import (
    get_chroma_client, get_or_create_collection, get_embedding_model
)
from app.core.config import settings

logger = structlog.get_logger(__name__)

RRF_K = 60

@dataclass
class SearchResult:
    chunk_id: str
    content: str
    source_filename: str
    score: float
    bm25_rank: Optional[int] = None
    vector_rank: Optional[int] = None

#BM25 Search
def _tokenize(text: str) -> list[str]:
    text = text.lower()
    tokens = re.findall(r'\b\w+\b', text)
    return tokens

def _bm25_search(
        query: str,
        chunks: list[dict],
        top_k: int
) -> list[tuple[int, float]]:
    """
    Run BM25 keyword search over a list of text chunks.
    Returns list of (chunk_index, score) sorted by score descending.
    """

    if not chunks:
        return []
    
    tokenized_corpus = [_tokenize(chunk["content"]) for chunk in chunks]
    bm25 = BM25Okapi(tokenized_corpus)

    tokenized_query = _tokenize(query)
    scores = bm25.get_scores(tokenized_query)

    ranked = sorted(
        enumerate(scores),
        key=lambda x: x[1],
        reverse=True,
    )

    ranked = [(idx, score) for idx, score in ranked if score > 0]

    return ranked[:top_k]

#Vector Search
async def _vector_search(
        query: str,
        user_id: str,
        top_k: int,
        collection,
        embedding_model
) -> list[dict]:
    """
    Run semantic vector search in ChromaDB.

    1. Embed the query using the same model used at ingestion time
    2. ChromaDB finds the closest vectors using cosine similarity
    3. Filter by user_id so users only see their own documents

    Returns list of chunk dicts with id, content, metadata, distance.
    """

    loop = asyncio.get_event_loop()
    query_embedding = await loop.run_in_executor(
        None, 
        lambda: embedding_model.get_text_embedding(query)
    )

    #Search ChromaDB
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"user_id": user_id},
        include=["documents", "metadatas", "distances"]
    )

    chunks = []
    if results["ids"] and results["ids"][0]:
        for i, chunk_id in enumerate(results["ids"][0]):
            chunks.append({
                "id": chunk_id,
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "similarity": 1 - results["distances"][0][i]
            })

    return chunks

#Reciprocal_rank_fusion(RRF)
def _reciprocal_rank_fusion(
        bm25_results: list[tuple[int, float]],
        vector_results: list[dict],
        all_chunks: list[dict],
        top_k: int
) -> list[SearchResult]:
    """
    Combine BM25 and vector results using Reciprocal Rank Fusion.

    RRF formula: score(d) = Σ 1 / (k + rank(d))

    For each document, sum the reciprocal of its rank in each list.
    Documents appearing at the top of both lists get the highest scores.
    Documents missing from one list get no contribution from that list.

    This is better than averaging scores because:
    - Ranks are comparable across methods
    - Raw scores (BM25 vs cosine) are on incompatible scales
    - RRF naturally handles documents appearing in only one list
    """

    rrf_scores: dict[str, float] = {}
    chunk_map: dict[str, dict] = {}

    #process BM25 ranks
    for rank, (chunk_idx, _) in enumerate(bm25_results):
        chunk = all_chunks[chunk_idx]
        chunk_id = chunk["id"]
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + (
            settings.keyword_weight / (RRF_K + rank + 1)
        )
        chunk_map[chunk_id] = chunk

     # Process vector ranks
    for rank, chunk in enumerate(vector_results):
        chunk_id = chunk["id"]
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + (
            settings.semantic_weight / (RRF_K + rank + 1)
        )
        if chunk_id not in chunk_map:
            chunk_map[chunk_id] = chunk

     # Sort by RRF score
    sorted_ids = sorted(
        rrf_scores.keys(),
        key=lambda cid: rrf_scores[cid],
        reverse=True,
    )[:top_k]

    # Build SearchResult objects
    results = []
    bm25_id_to_rank = {
        all_chunks[idx]["id"]: rank
        for rank, (idx, _) in enumerate(bm25_results)
    }
    vector_id_to_rank = {
        chunk["id"]: rank
        for rank, chunk in enumerate(vector_results)
    }

    for chunk_id in sorted_ids:
        chunk = chunk_map[chunk_id]
        metadata = chunk.get("metadata", {})
        results.append(SearchResult(
            chunk_id=chunk_id,
            content=chunk["content"],
            source_filename=metadata.get("filename", "Unknown"),
            score=rrf_scores[chunk_id],
            bm25_rank=bm25_id_to_rank.get(chunk_id),
            vector_rank=vector_id_to_rank.get(chunk_id),
        ))

    return results

async def hybrid_search(
        query: str,
        user_id: str,
        top_k: int = None
) -> list[SearchResult]:
    """
    Run hybrid search: BM25 + vector, fused with RRF.

    This is called by the RAG tool inside the agent.

    Steps:
      1. Get all candidate chunks for this user from ChromaDB
      2. Run BM25 over those chunks
      3. Run vector search in ChromaDB
      4. Fuse results with RRF
      5. Return top_k results

    Returns empty list gracefully if no documents uploaded yet.
    """
    if top_k is None:
        top_k = settings.hybrid_search_top_k

    logger.info(
        "hybrid_search.starting",
        query=query[:100],
        user_id=user_id,
        top_k=top_k
    )

    try:
        client = get_chroma_client()
        collection = get_or_create_collection(client)
        embedding_model = get_embedding_model()

        fetch_limit = min(top_k * 10, 100)

        all_results = collection.get(
            where={"user_id": user_id},
            limit=fetch_limit,
            include=["documents", "metadatas"]
        )

        if not all_results["ids"]:
            logger.info("hybrid_search.no_documents", user_id=user_id)
            return []
        
        all_chunks = [
            {
                "id": all_results["ids"][i],
                "content": all_results["documents"][i],
                "metadata": all_results["metadatas"][i],
            }
            for i in range(len(all_results["ids"]))
        ]

        #BM25 keyword search (sync — runs fast in-memory)
        bm25_results = _bm25_search(
            query=query,
            chunks=all_chunks,
            top_k=top_k * 2
        )

        #Vector semantic search (async — hits ChromaDB)
        vector_results = await _vector_search(
            query=query,
            user_id=user_id,
            top_k=top_k * 2,
            collection=collection,
            embedding_model=embedding_model,
        )

        #Reciprocal Rank Fusion
        fused = _reciprocal_rank_fusion(
            bm25_results=bm25_results,
            vector_results=vector_results,
            all_chunks=all_chunks,
            top_k=top_k,
        )

        logger.info(
            "hybrid_search.complete",
            query=query[:100],
            bm25_hits=len(bm25_results),
            vector_hits=len(vector_results),
            fused_results=len(fused),
        )
        return fused
    
    except Exception as e:
        logger.error("hybrid_search.error", error=str(e))
        return []
