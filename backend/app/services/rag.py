import asyncio
import json
import uuid
from pypdf import PdfReader
from docx import Document as DocxDocument
from sqlalchemy import select
import structlog
from langchain_core.tools import tool
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.document import Document
from app.services.hybrid_search import hybrid_search
from app.services.vector_store import (
    get_chroma_client, get_or_create_collection, get_embedding_model
)

logger = structlog.get_logger(__name__)

CHUNK_SIZE = 512
CHUNK_OVERLAP = 50

#TEXT EXTRACTION
def _extract_text_from_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    pages = []

    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text.strip())
    return "\n\n".join(pages)

def _extract_text_from_docx(file_path: str) -> str:
    doc = DocxDocument(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)

def _extract_text_from_txt(file_path: str) -> str:
    with open(file_path, "r" ,encoding="utf-8", errors="ignore") as f:
        return f.read()
    
def _extract_text(file_path: str, file_type: str) -> str:
    extractors = {
        "pdf":_extract_text_from_pdf,
        "docx":_extract_text_from_docx,
        "txt":_extract_text_from_txt,
        "md":_extract_text_from_txt,
        "cv":_extract_text_from_txt,
    }
    extractor = extractors.get(file_type)
    if not extractor:
        raise ValueError(f"Unsupported file type: {file_type}")
    return extractor(file_path)

#TEXT CHUNKING
def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into overlapping chunks by word count.
    We use word-based splitting (not token-based) for simplicity —
    roughly 1 token ≈ 0.75 words, so chunk_size=512 tokens ≈ 384 words.
    """

    words = text.split()
    if not words:
        return []
    
    words_per_chunk = int(chunk_size * 0.75)
    words_overlap = int(overlap * 0.75)
    if words_overlap >= words_per_chunk:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks = []
    start = 0

    while start < len(words):
        end = start + words_per_chunk
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))

        start += words_per_chunk - words_overlap

        if start >= len(words):
            break

    return chunks

#DOCUMENT INGESTION
async def ingest_document(
        document_id: str,
        file_path: str,
        file_type: str,
        user_id: str,
        filename: str,
) -> None:
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Document).where(Document.id == uuid.UUID(document_id))
            )
            doc = result.scalar_one_or_none()
        except Exception as e:
            logger.error("ingest.lookup_failed", document_id=document_id, error=str(e))
            return
        if not doc:
            logger.error("ingest.document_not_found", document_id=document_id)
            return
        try:
            doc.status = "processing"
            await db.commit()

            logger.info(
                "ingest.started",
                document_id=document_id,
                filename=filename,
                file_type=file_type
            )

            #Extract text (CPU bound)
            loop = asyncio.get_running_loop()
            raw_text = await loop.run_in_executor(
                None,
                lambda:_extract_text(file_path, file_type)
            )
            if not raw_text.strip():
                raise ValueError("Document appears to be empty or unreadable")
            
            #split into chunks
            chunks = _chunk_text(raw_text)
            logger.info(
                "ingest.chunked",
                document_id=document_id,
                chunk_count=len(chunks)
            )

            #Embed and store in ChromaDB
            chunk_ids = await _embed_and_store(
                chunks=chunks,
                document_id=document_id,
                user_id=user_id,
                filename=filename
            )

            #Update DB to ready
            doc.status = "ready"
            doc.chunk_count = len(chunks)
            doc.chroma_doc_ids = json.dumps(chunk_ids)
            await db.commit()

            logger.info(
                "ingest.complete",
                document_id=document_id,
                chunk_count=len(chunks)
            )
        except Exception as e:
            logger.exception(
                "ingest.failed",
                document_id=document_id,
                error=str(e),
            )

    # Clear any failed transaction before recording failure state.
            await db.rollback()

            doc.status = "failed"
            doc.error_message = str(e)

            await db.commit()


async def _embed_and_store(
    chunks: list[str],
    document_id: str,
    user_id: str,
    filename: str,
) -> list[str]:
    client = get_chroma_client()

    loop = asyncio.get_running_loop()

    collection = await loop.run_in_executor(
        None,
        lambda: get_or_create_collection(client),
    )

    embedding_model = await loop.run_in_executor(
        None,
        get_embedding_model,
    )

    chunk_ids = [f"{document_id}_chunk_{i}" for i in range(len(chunks))]

    metadatas = [
        {
            "document_id": document_id,
            "user_id": user_id,
            "filename": filename,
            "chunk_index": i,
        }
        for i in range(len(chunks))
    ]

    BATCH_SIZE = 32

    for batch_start in range(0, len(chunks), BATCH_SIZE):
        batch_chunks = chunks[batch_start:batch_start + BATCH_SIZE]
        batch_ids = chunk_ids[batch_start:batch_start + BATCH_SIZE]
        batch_metadatas = metadatas[batch_start:batch_start + BATCH_SIZE]

        embeddings = await loop.run_in_executor(
            None,
            lambda b=batch_chunks: [
                embedding_model.get_text_embedding(chunk)
                for chunk in b
            ],
        )

        await loop.run_in_executor(
            None,
            lambda: collection.add(
                ids=batch_ids,
                embeddings=embeddings,
                documents=batch_chunks,
                metadatas=batch_metadatas,
            ),
        )

        logger.info(
            "ingest.batch_stored",
            batch=f"{batch_start}-{batch_start + len(batch_chunks)}",
        )

    return chunk_ids

async def delete_document_vectors(document_id: str, chroma_doc_ids: list[str]) -> None:
    try:
        client = get_chroma_client()
        collection = get_or_create_collection(client)
        collection.delete(ids=chroma_doc_ids)
        logger.info(
            "vectors.deleted",
            document_id=document_id,
            chunk_count=len(chroma_doc_ids),
        )
    except Exception as e:
        logger.error("vectors.delete_failed", document_id=document_id, error=str(e))

#RAG TOOL
async def _rag_search(query: str, user_id: str) -> dict:
    results = await hybrid_search(query=query, user_id=user_id)

    if not results:
        return {
            "content": "No relevant documents found for this query",
            "citations": []
        }
    
    context_parts = []
    citations = []

    for i, result in enumerate(results):
        context_parts.append(
            f"[Source {i+1}: {result.source_filename}]\n{result.content}"
        )
        citations.append({
            "index": i + 1,
            "filename": result.source_filename,
            "snippet": result.content[:200] + "..." if len(result.content) > 200 else result.content,
            "score": round(result.score, 4),
        })

    context = "\n\n---\n\n".join(context_parts)
    full_content = (
        f"Here is relevant context from the user's documents:\n\n"
        f"{context}\n\n"
        f"Use this information to answer the user's question. "
        f"Cite sources as [Source N]."
        )

    return {
        "content": full_content,
        "citations": citations,
    }

def make_rag_tool(user_id: str):
    @tool
    async def rag_search(query: str) -> dict:
        """
        Search the user's uploaded documents for relevant information.
        Use this when the user asks about their documents or uploaded files.
        Input should be a clear search query.
        """
        return await _rag_search(query=query, user_id=user_id)
    return rag_search

@tool
async def rag_search_tool(query: str) -> dict:
    """
    Search uploaded documents for relevant information.
    Use when the user asks about their documents.
    """
    return {
        "content": "RAG search requires user context. Use make_rag_tool(user_id) instead.",
        "citations": [],
    }
    




