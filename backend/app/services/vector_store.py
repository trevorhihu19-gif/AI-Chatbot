import structlog
import chromadb
from chromadb.config import Settings as ChromaSettings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from app.core.config import settings

logger = structlog.get_logger(__name__)

DOCUMENTS_COLLECTION = "surge_documents"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

def get_chroma_client() -> chromadb.HttpClient:
    client = chromadb.HttpClient(
        host=settings.chroma_host,
        port=settings.chroma_port,
        settings=ChromaSettings(anonymized_telemetry=False)
    )
    return client

def get_or_create_collection(client: chromadb.HttpClient) -> chromadb.Collection:
    collection = client.get_or_create_collection(
        name=DOCUMENTS_COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )
    logger.info(
        "chroma.collection.ready",
        name=DOCUMENTS_COLLECTION,
        count=collection.count()
    )
    return collection

def get_embedding_model():
    return HuggingFaceEmbedding(model_name=EMBEDDING_MODEL)
