import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import logging
from backend.app.config import settings
from backend.app.services.ingestion import ingestion_engine
from backend.app.services.vector_store import vector_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("corpus_indexer")


async def main():
    logger.info("Initializing vector store collection...")
    vector_service.ensure_collection()

    corpus_dir = settings.CORPUS_DIR
    if not corpus_dir.exists():
        logger.error(f"Corpus directory not found: {corpus_dir}")
        return

    # Files to index in corpus
    files = sorted(list(corpus_dir.glob("*.*")))
    valid_files = [
        f for f in files
        if f.suffix.lower() in [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".md", ".txt"]
    ]

    logger.info(f"Found {len(valid_files)} documents to ingest in {corpus_dir}")

    for f in valid_files:
        logger.info(f"--- Ingesting: {f.name} ---")
        try:
            doc_record = await ingestion_engine.ingest_file(f)
            logger.info(
                f"Successfully ingested {f.name}: {doc_record['page_count']} pages, "
                f"{doc_record['chunk_count']} chunks, {doc_record['ocr_pages']} OCR pages."
            )
        except Exception as e:
            logger.error(f"Failed to ingest {f.name}: {str(e)}", exc_info=True)

    logger.info("All corpus documents have been processed and indexed.")


if __name__ == "__main__":
    asyncio.run(main())
