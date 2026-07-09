import json
import os
import uuid
import aiofiles
import structlog
from fastapi import (
    APIRouter, 
    BackgroundTasks,
    Depends,
    HTTPException,
    UploadFile,
    status
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, transaction
from app.core.security import get_current_user, sanitize_filename, validate_upload_file
from app.services.rag import ingest_document
from app.services.rag import delete_document_vectors
from app.models.document import Document
from app.models.user import User
from app.schemas.document import DocumentOut
from app.core.config import settings

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile,
    background_task: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
): 
    file_ext, file_content = await validate_upload_file(file)

    original_filename = file.filename or "upload"
    safe_name = sanitize_filename(original_filename)

    unique_prefix = str(uuid.uuid4())[:8]
    stored_filename = f"{unique_prefix}_{safe_name}"
    file_path = os.path.join(settings.upload_dir, stored_filename)
    
    os.makedirs(settings.upload_dir, exist_ok=True)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(file_content)

    logger.info(
        "document.saved",
        filename=original_filename,
        stored_as=stored_filename,
        size_bytes=len(file_content),
        user_id=str(current_user.id)
    )

    document = Document(
        user_id=current_user.id,
        filename=original_filename,
        stored_filename=stored_filename,
        file_type=file_ext,
        size_bytes=len(file_content),
        chroma_collection=settings.chroma_host,
        status="pending",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    background_task.add_task(
        _run_ingestion,
        document_id=str(document.id),
        file_path=file_path,
        file_type=file_ext,
        user_id=str(current_user.id),
        filename=original_filename
    )

    logger.info(
        "document.upload_complete",
        document_id=str(document.id),
        filename=original_filename
    )
    return document

async def _run_ingestion(
        document_id: str,
        file_path: str,
        file_type: str,
        user_id: str,
        filename: str,
) -> None:
    try:
        await ingest_document(
            document_id=document_id,
            file_path=file_path,
            file_type=file_type,
            user_id=user_id,
            filename=filename
        )
    except Exception as e:
        logger.error(
            "document.ingestion_task_failed",
            document_id=document_id,
            error=str(e)
        )

@router.get("", response_model=list[DocumentOut])
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    documents = result.scalars().all()
    return documents

@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    return document

@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    if document.chroma_doc_ids:
        try:
            chunk_ids = json.loads(document.chroma_doc_ids)
            await delete_document_vectors(
                document_id=str(document.id),
                chroma_doc_ids=chunk_ids,
            )
        except Exception as e:
            logger.error(
                "document.chroma_delete_failed",
                document_id=str(document.id),
                error=str(e)
            )

    file_path = os.path.join(settings.upload_dir, document.stored_filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info("document.file_deleted", path=file_path)
        except Exception as e:
            logger.error("document.file_delete_failed", path=file_path, error=str(e))

    async with transaction(db):
        await db.delete(document)

    logger.info(
        "document.deleted",
        document_id=str(document_id),
        user_id=str(current_user.id)
    )

