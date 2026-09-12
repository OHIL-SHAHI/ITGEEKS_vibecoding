import time
import shutil
import logging
import asyncio
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import FileResponse

from backend.app.config import settings
from backend.app.services.mongo_store import mongo_store
from backend.app.services.vector_store import vector_service
from backend.app.services.ingestion import ingestion_engine
from backend.app.models.schemas import DocumentListResponse, DocumentItem

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/corpus", tags=["corpus"])


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents():
    try:
        raw_docs = await mongo_store.list_documents()
        docs = [DocumentItem(**d) for d in raw_docs]
        total_pages = sum(d.page_count for d in docs)
        total_chunks = sum(d.chunk_count for d in docs)
        return DocumentListResponse(
            documents=docs,
            total_documents=len(docs),
            total_pages=total_pages,
            total_chunks=total_chunks
        )
    except Exception as e:
        logger.error(f"Failed to list documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(file: UploadFile = File(...)):
    try:
        filename = file.filename
        suffix = Path(filename).suffix.lower()
        if suffix not in [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".md", ".txt"]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format '{suffix}'. Allowed: PDF, PNG, JPG, WEBP, MD, TXT."
            )

        dest_dir = settings.UPLOADS_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / filename

        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        safe_name = "".join([c if c.isalnum() else "_" for c in Path(filename).stem])
        doc_id = f"{safe_name}_{int(time.time())}"

        fmt = "pdf" if suffix == ".pdf" else ("handwritten_scan" if suffix in [".png", ".jpg", ".jpeg", ".webp"] else "text")

        # Create initial record in MongoDB
        initial_record = {
            "doc_id": doc_id,
            "filename": filename,
            "format": fmt,
            "page_count": 0,
            "chunk_count": 0,
            "ocr_pages": 0,
            "status": "processing",
            "progress": 5,
            "status_message": f"Received {filename}. Queued for ingestion...",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        await mongo_store.upsert_document(initial_record)

        # Dispatch asynchronous ingestion task
        asyncio.create_task(ingestion_engine.ingest_file(dest_path, doc_id))

        return {
            "status": "processing",
            "doc_id": doc_id,
            "filename": filename,
            "message": f"Document '{filename}' uploaded successfully. Ingestion in progress."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/status/{doc_id}")
async def get_document_status(doc_id: str):
    doc = await mongo_store.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")
    return {
        "doc_id": doc.get("doc_id"),
        "filename": doc.get("filename"),
        "status": doc.get("status", "ready"),
        "progress": doc.get("progress", 100),
        "status_message": doc.get("status_message", "Ready"),
        "error_message": doc.get("error_message")
    }


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    doc = await mongo_store.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        # 1. Delete points in vector store
        vector_service.delete_by_doc_id(doc_id)

        # 2. Delete page preview images
        page_dir = settings.PAGES_DIR / doc_id
        if page_dir.exists():
            shutil.rmtree(page_dir, ignore_errors=True)

        # 3. Delete metadata in MongoDB
        await mongo_store.delete_document(doc_id)

        return {
            "status": "success",
            "message": f"Document '{doc.get('filename')}' ({doc_id}) deleted successfully."
        }
    except Exception as e:
        logger.error(f"Failed to delete document {doc_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    doc = await mongo_store.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


@router.get("/pages/{doc_id}/{page_num}/image")
async def get_page_image(doc_id: str, page_num: int):
    img_path = settings.PAGES_DIR / doc_id / f"page_{page_num}.png"
    if not img_path.exists():
        raise HTTPException(status_code=404, detail=f"Page image not found: {img_path.name}")
    return FileResponse(str(img_path), media_type="image/png")
