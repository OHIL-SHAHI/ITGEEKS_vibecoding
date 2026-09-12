import re
import time
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from langchain_qdrant import QdrantVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document

from backend.app.config import settings

logger = logging.getLogger(__name__)


class VectorServiceRateLimitError(Exception):
    pass


class VectorService:
    def __init__(self):
        self._client: Optional[QdrantClient] = None
        self._embeddings: Optional[GoogleGenerativeAIEmbeddings] = None
        self._vector_store: Optional[QdrantVectorStore] = None

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(url=settings.QDRANT_URL)
        return self._client

    @property
    def embeddings(self) -> GoogleGenerativeAIEmbeddings:
        if self._embeddings is None:
            self._embeddings = GoogleGenerativeAIEmbeddings(
                model=settings.EMBEDDING_MODEL,
                google_api_key=settings.GEMINI_API_KEY
            )
        return self._embeddings

    def ensure_collection(self, vector_dim: int = 3072) -> None:
        try:
            collections = self.client.get_collections().collections
            existing_names = [c.name for c in collections]
            if settings.QDRANT_COLLECTION in existing_names:
                info = self.client.get_collection(settings.QDRANT_COLLECTION)
                existing_dim = info.config.params.vectors.size
                if existing_dim != vector_dim:
                    logger.warning(
                        f"Collection dim mismatch (existing {existing_dim} vs required {vector_dim}). Recreating..."
                    )
                    self.client.delete_collection(settings.QDRANT_COLLECTION)
                    existing_names.remove(settings.QDRANT_COLLECTION)

            if settings.QDRANT_COLLECTION not in existing_names:
                logger.info(f"Creating Qdrant collection '{settings.QDRANT_COLLECTION}' with dim {vector_dim}")
                self.client.create_collection(
                    collection_name=settings.QDRANT_COLLECTION,
                    vectors_config=qmodels.VectorParams(
                        size=vector_dim,
                        distance=qmodels.Distance.COSINE
                    )
                )
            else:
                logger.info(f"Collection '{settings.QDRANT_COLLECTION}' ready.")
        except Exception as e:
            logger.error(f"Error checking/creating Qdrant collection: {str(e)}")
            raise

    def get_vector_store(self) -> QdrantVectorStore:
        if self._vector_store is None:
            self.ensure_collection()
            self._vector_store = QdrantVectorStore(
                client=self.client,
                collection_name=settings.QDRANT_COLLECTION,
                embedding=self.embeddings,
            )
        return self._vector_store

    async def add_documents_throttled_async(
        self,
        docs: List[Document],
        batch_size: int = 35,
        delay_seconds: float = 2.5,
        progress_callback=None
    ) -> int:
        if not docs:
            return 0

        vs = self.get_vector_store()
        total_docs = len(docs)
        logger.info(f"Indexing {total_docs} document chunks into Qdrant asynchronously (batch size: {batch_size})...")

        for i in range(0, total_docs, batch_size):
            batch = docs[i:i + batch_size]
            success = False
            for attempt in range(8):
                try:
                    await asyncio.to_thread(vs.add_documents, batch)
                    success = True
                    break
                except Exception as e:
                    err_msg = str(e).lower()
                    if "429" in err_msg or "resource_exhausted" in err_msg or "quota" in err_msg:
                        # Extract exact retry delay from Google API error if provided
                        match = re.search(r'retry(?:ing)?\s*(?:in|delay)?\s*[:\s]*(\d+(?:\.\d+)?)s?', err_msg)
                        if match:
                            backoff = float(match.group(1)) + 2.0
                        else:
                            backoff = min(60.0, 4.0 * (1.8 ** attempt))
                        logger.warning(
                            f"Rate limit hit during chunk indexing (batch {i}-{i+len(batch)}, attempt {attempt+1}/8). "
                            f"Backing off for {backoff:.1f}s..."
                        )
                        await asyncio.sleep(backoff)
                    else:
                        logger.error(f"Failed to index batch {i}-{i+len(batch)}: {str(e)}")
                        raise

            if not success:
                raise RuntimeError(f"Exceeded retries while indexing batch {i}-{i+len(batch)}")

            processed = min(i + batch_size, total_docs)
            logger.info(f"Indexed {processed}/{total_docs} chunks")
            if progress_callback:
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback(processed, total_docs)
                else:
                    progress_callback(processed, total_docs)

            if processed < total_docs and delay_seconds > 0:
                await asyncio.sleep(delay_seconds)

        return total_docs

    def add_documents_throttled(
        self,
        docs: List[Document],
        batch_size: int = 35,
        delay_seconds: float = 3.0
    ) -> int:
        if not docs:
            return 0

        vs = self.get_vector_store()
        total_docs = len(docs)
        logger.info(f"Indexing {total_docs} document chunks into Qdrant...")

        for i in range(0, total_docs, batch_size):
            batch = docs[i:i + batch_size]
            success = False
            for attempt in range(8):
                try:
                    vs.add_documents(batch)
                    success = True
                    break
                except Exception as e:
                    err_msg = str(e).lower()
                    if "429" in err_msg or "resource_exhausted" in err_msg or "quota" in err_msg:
                        match = re.search(r'retry(?:ing)?\s*(?:in|delay)?\s*[:\s]*(\d+(?:\.\d+)?)s?', err_msg)
                        if match:
                            backoff = float(match.group(1)) + 2.0
                        else:
                            backoff = min(60.0, 4.0 * (1.8 ** attempt))
                        logger.warning(
                            f"Rate limit hit during chunk indexing (attempt {attempt+1}/8). "
                            f"Backing off for {backoff:.1f}s..."
                        )
                        time.sleep(backoff)
                    else:
                        logger.error(f"Failed to index batch {i}-{i+len(batch)}: {str(e)}")
                        raise

            if not success:
                raise RuntimeError(f"Exceeded retries while indexing batch {i}-{i+len(batch)}")

            processed = min(i + batch_size, total_docs)
            logger.info(f"Indexed {processed}/{total_docs} chunks")
            if processed < total_docs and delay_seconds > 0:
                time.sleep(delay_seconds)

        return total_docs

    def delete_by_doc_id(self, doc_id: str) -> None:
        try:
            self.client.delete(
                collection_name=settings.QDRANT_COLLECTION,
                points_selector=qmodels.FilterSelector(
                    filter=qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="metadata.doc_id",
                                match=qmodels.MatchValue(value=doc_id)
                            )
                        ]
                    )
                )
            )
            logger.info(f"Deleted vector points for doc_id: {doc_id}")
        except Exception as e:
            logger.error(f"Failed to delete points for doc_id {doc_id}: {str(e)}")


    def similarity_search_with_score(
        self,
        query: str,
        k: int = 8,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Document, float]]:
        vs = self.get_vector_store()

        for attempt in range(4):
            try:
                if filter_dict:
                    return vs.similarity_search_with_score(query=query, k=k, filter=filter_dict)
                return vs.similarity_search_with_score(query=query, k=k)
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str:
                    backoff = 2.0 * (attempt + 1)
                    logger.warning(f"Rate limit hit during similarity search. Attempt {attempt+1}/4. Backing off {backoff}s...")
                    time.sleep(backoff)
                else:
                    logger.error(f"Similarity search error: {str(e)}")
                    return []

        logger.error("Rate limit exceeded repeatedly during similarity search.")
        raise VectorServiceRateLimitError("The AI embedding service is temporarily rate-limited. Please retry shortly.")


vector_service = VectorService()
