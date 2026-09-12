import os
import time
import base64
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Callable
import pymupdf  # fitz
from PIL import Image

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI

from backend.app.config import settings
from backend.app.services.vector_store import vector_service
from backend.app.services.mongo_store import mongo_store

logger = logging.getLogger(__name__)

TRANSCRIPTION_PROMPT = (
    "Transcribe all handwritten and printed text on this page exactly as written. "
    "Preserve structure (headings, bullet points, equations) where possible. "
    "Do not add commentary, only output the transcription."
)


class IngestionEngine:
    def __init__(self):
        self._vlm = None
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP
        )

    @property
    def vlm(self):
        if self._vlm is None:
            self._vlm = ChatGoogleGenerativeAI(
                model=settings.OCR_MODEL,
                google_api_key=settings.GEMINI_API_KEY
            )
        return self._vlm

    async def transcribe_image_b64_async(self, image_b64: str) -> str:
        message = HumanMessage(
            content=[
                {"type": "text", "text": TRANSCRIPTION_PROMPT},
                {
                    "type": "image_url",
                    "image_url": f"data:image/png;base64,{image_b64}",
                },
            ]
        )
        for attempt in range(4):
            try:
                response = await asyncio.to_thread(self.vlm.invoke, [message])
                content = response.content
                if isinstance(content, list):
                    parts = []
                    for part in content:
                        if isinstance(part, str):
                            parts.append(part)
                        elif isinstance(part, dict) and "text" in part:
                            parts.append(part["text"])
                    content = "\n".join(parts)
                return content.strip() if isinstance(content, str) else str(content)
            except Exception as e:
                err_msg = str(e).lower()
                if "429" in err_msg or "resource_exhausted" in err_msg or "quota" in err_msg:
                    backoff = 4.0 * (attempt + 1)
                    logger.warning(f"Rate limit in VLM OCR. Attempt {attempt + 1}/4. Backing off {backoff}s...")
                    await asyncio.sleep(backoff)
                else:
                    logger.error(f"VLM OCR transcription failed: {str(e)}")
                    if attempt == 3:
                        return ""
                    await asyncio.sleep(2.0)
        return ""

    def transcribe_image_b64(self, image_b64: str) -> str:
        return asyncio.run(self.transcribe_image_b64_async(image_b64))

    async def process_pdf_async(
        self,
        file_path: Path,
        doc_id: str,
        progress_callback: Optional[Callable[[int, int, str], Any]] = None
    ) -> Tuple[List[Document], int, int]:
        """
        Process PDF asynchronously: extract text per page, trigger Gemini OCR if text < MIN_CHARS_THRESHOLD,
        save rendered page images, report progress, return (documents, page_count, ocr_count).
        """
        doc = pymupdf.open(file_path)
        page_count = len(doc)
        doc.close()

        page_documents = []
        ocr_count = 0
        pages_out_dir = settings.PAGES_DIR / doc_id
        pages_out_dir.mkdir(parents=True, exist_ok=True)

        doc = pymupdf.open(file_path)
        for page_idx in range(page_count):
            page = doc[page_idx]
            raw_text = page.get_text().strip()
            page_num_1indexed = page_idx + 1
            page_img_path = pages_out_dir / f"page_{page_num_1indexed}.png"

            # Render page image for viewer
            mat = pymupdf.Matrix(settings.DPI_SCALE, settings.DPI_SCALE)
            pix = page.get_pixmap(matrix=mat)
            pix.save(str(page_img_path))
            png_bytes = pix.tobytes("png")
            image_b64 = base64.b64encode(png_bytes).decode("utf-8")

            # Check if OCR is required
            # 1. Text is shorter than threshold
            # 2. Text has fewer than 4 whitespace-separated alphanumeric tokens (scanner watermark / page number only)
            words = [w for w in raw_text.split() if any(c.isalnum() for c in w)]
            needs_ocr = len(raw_text) < settings.MIN_CHARS_THRESHOLD or len(words) < 4

            is_ocr = False
            text = raw_text

            if needs_ocr:
                logger.info(f"Page {page_num_1indexed} of {file_path.name} needs OCR. Transcribing...")
                if progress_callback:
                    await progress_callback(
                        page_num_1indexed, page_count,
                        f"Page {page_num_1indexed}/{page_count}: Performing VLM OCR..."
                    )
                ocr_text = await self.transcribe_image_b64_async(image_b64)
                if ocr_text:
                    text = ocr_text
                    is_ocr = True
                    ocr_count += 1
                # Small pause to avoid hitting VLM rate limits
                await asyncio.sleep(1.0)
            else:
                if progress_callback:
                    await progress_callback(
                        page_num_1indexed, page_count,
                        f"Page {page_num_1indexed}/{page_count}: Extracted digital text."
                    )

            if not text:
                text = f"[Page {page_num_1indexed} blank or unreadable]"

            rel_image_url = f"/api/corpus/pages/{doc_id}/{page_num_1indexed}/image"

            d = Document(
                page_content=text,
                metadata={
                    "source": str(file_path),
                    "filename": file_path.name,
                    "doc_id": doc_id,
                    "page": page_num_1indexed,
                    "page_label": str(page_num_1indexed),
                    "ocr": is_ocr,
                    "image_url": rel_image_url
                }
            )
            page_documents.append(d)

        doc.close()
        return page_documents, page_count, ocr_count

    async def process_image_async(
        self,
        file_path: Path,
        doc_id: str,
        progress_callback: Optional[Callable[[int, int, str], Any]] = None
    ) -> Tuple[List[Document], int, int]:
        pages_out_dir = settings.PAGES_DIR / doc_id
        pages_out_dir.mkdir(parents=True, exist_ok=True)
        target_img_path = pages_out_dir / "page_1.png"

        # Convert/Save as PNG
        with Image.open(file_path) as img:
            img.convert("RGB").save(str(target_img_path), format="PNG")

        image_bytes = target_img_path.read_bytes()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        if progress_callback:
            await progress_callback(1, 1, "Transcribing handwritten scan via VLM OCR...")

        logger.info(f"Running OCR on handwritten image {file_path.name}...")
        transcribed = await self.transcribe_image_b64_async(image_b64)
        if not transcribed:
            transcribed = f"[Handwritten image {file_path.name} transcription failed]"

        rel_image_url = f"/api/corpus/pages/{doc_id}/1/image"

        doc = Document(
            page_content=transcribed,
            metadata={
                "source": str(file_path),
                "filename": file_path.name,
                "doc_id": doc_id,
                "page": 1,
                "page_label": "1",
                "ocr": True,
                "image_url": rel_image_url
            }
        )
        return [doc], 1, 1

    async def process_text_or_markdown_async(
        self,
        file_path: Path,
        doc_id: str
    ) -> Tuple[List[Document], int, int]:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        doc = Document(
            page_content=content,
            metadata={
                "source": str(file_path),
                "filename": file_path.name,
                "doc_id": doc_id,
                "page": 1,
                "page_label": "1",
                "ocr": False,
                "image_url": None
            }
        )
        return [doc], 1, 0

    async def ingest_file(self, file_path: Path, doc_id: str = None) -> Dict[str, Any]:
        """
        Ingest any supported file format asynchronously, split into chunks,
        index in Qdrant, and update real-time status in MongoDB.
        """
        if not doc_id:
            safe_name = "".join([c if c.isalnum() else "_" for c in file_path.stem])
            doc_id = f"{safe_name}_{int(time.time())}"

        # Initialize status in MongoDB
        await mongo_store.update_document_status(
            doc_id=doc_id,
            status="processing",
            progress=5,
            status_message=f"Starting analysis of {file_path.name}..."
        )

        try:
            suffix = file_path.suffix.lower()

            async def on_page_progress(current: int, total: int, desc: str):
                pct = 10 + int((current / max(1, total)) * 40)
                await mongo_store.update_document_status(
                    doc_id=doc_id,
                    status="processing",
                    progress=pct,
                    status_message=desc
                )

            if suffix in [".pdf"]:
                raw_docs, page_count, ocr_count = await self.process_pdf_async(file_path, doc_id, on_page_progress)
                fmt = "pdf"
            elif suffix in [".png", ".jpg", ".jpeg", ".webp"]:
                raw_docs, page_count, ocr_count = await self.process_image_async(file_path, doc_id, on_page_progress)
                fmt = "handwritten_scan"
            elif suffix in [".md", ".markdown", ".txt"]:
                raw_docs, page_count, ocr_count = await self.process_text_or_markdown_async(file_path, doc_id)
                fmt = "markdown" if suffix in [".md", ".markdown"] else "text"
            else:
                raise ValueError(f"Unsupported document format: {suffix}")

            # Split into chunks
            await mongo_store.update_document_status(
                doc_id=doc_id,
                status="processing",
                progress=55,
                status_message=f"Splitting {page_count} pages into semantic chunks..."
            )
            raw_chunks = self.text_splitter.split_documents(raw_docs)

            # Prepend context to chunk content so semantic search matches filename, page, and topics
            contextualized_chunks = []
            for chunk in raw_chunks:
                fn = chunk.metadata.get("filename", file_path.name)
                pg = chunk.metadata.get("page", 1)
                prefix = f"[Document: {fn} | Page: {pg}]\n"
                chunk.page_content = prefix + chunk.page_content.strip()
                contextualized_chunks.append(chunk)

            logger.info(f"Split {file_path.name} ({page_count} pages) into {len(contextualized_chunks)} contextualized chunks")

            # Asynchronously index into Qdrant in throttled batches
            async def on_batch_progress(indexed_so_far: int, total_chunks: int, custom_msg: str = None):
                pct = 60 + int((indexed_so_far / max(1, total_chunks)) * 35)
                msg = custom_msg or f"Embedding chunks into vector store ({indexed_so_far}/{total_chunks})..."
                await mongo_store.update_document_status(
                    doc_id=doc_id,
                    status="processing",
                    progress=pct,
                    status_message=msg
                )

            await vector_service.add_documents_throttled_async(
                contextualized_chunks,
                batch_size=25,
                delay_seconds=2.0,
                progress_callback=on_batch_progress
            )

            # Finalize metadata record in MongoDB
            doc_record = {
                "doc_id": doc_id,
                "filename": file_path.name,
                "format": fmt,
                "page_count": page_count,
                "chunk_count": len(contextualized_chunks),
                "ocr_pages": ocr_count,
                "status": "ready",
                "progress": 100,
                "status_message": "Document ready and fully indexed.",
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
            await mongo_store.upsert_document(doc_record)
            logger.info(f"Successfully finished ingestion for {file_path.name} ({doc_id})")
            return doc_record

        except Exception as e:
            logger.error(f"Ingestion failed for {file_path.name} ({doc_id}): {str(e)}", exc_info=True)
            await mongo_store.update_document_status(
                doc_id=doc_id,
                status="failed",
                progress=0,
                status_message="Ingestion failed.",
                error_message=str(e)
            )
            raise


ingestion_engine = IngestionEngine()
