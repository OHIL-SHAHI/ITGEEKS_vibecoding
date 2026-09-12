import os
import re
import logging
from typing import List, Dict, Any, Tuple, Optional
from openai import OpenAI
from langchain_core.documents import Document

from backend.app.config import settings
from backend.app.services.vector_store import vector_service, VectorServiceRateLimitError
from backend.app.services.mongo_store import mongo_store
from backend.app.models.schemas import SourceCitation, ChatQueryResponse

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """You are an exam-night study assistant. Answer the student question strictly and factually using ONLY the provided course material excerpts below.

CRITICAL INSTRUCTIONS:
1. Grounding: Every factual claim in your answer must be directly supported by the context excerpts. Do not extrapolate, speculate, or use parametric knowledge.
2. Summary & Topic Queries: If the student asks about topics, concepts, or summaries covered in a document or subject, extract and synthesize the key concepts explicitly present in the excerpts.
3. Refusal: If the provided excerpts do not contain enough information to answer the question, or if the question asks about concepts completely absent from the excerpts, you MUST output EXACTLY:
The requested information is not covered in the provided course materials.
Do not add any apology, explanation, or conversational commentary to this refusal.
4. Clean Prose Without Inline Citations: Do NOT include inline citations, bracketed tags, or source file annotations (such as [filename, Page N] or [Page N]) within your answer text. Provide clear, direct, well-structured factual prose. The UI automatically displays verified citations separately.
5. Multi-document synthesis: If the question requires combining evidence across different documents or pages, combine them coherently.
6. Tone: Concise, factual, academic. No greetings, no conversational filler. ZERO emojis under any circumstance.

Course Material Excerpts:
{context}
"""


class RagService:
    def __init__(self):
        self._client = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=settings.GEMINI_API_KEY,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
        return self._client

    async def retrieve_context(self, query: str, k: int = 10) -> List[Tuple[Document, float]]:
        """
        Retrieve relevant chunks from Qdrant vector store based on semantic similarity.
        """
        return vector_service.similarity_search_with_score(query=query, k=k)

    def format_context_blocks(self, scored_docs: List[Tuple[Document, float]]) -> str:
        blocks = []
        for doc, score in scored_docs:
            filename = doc.metadata.get("filename", "unknown")
            page = doc.metadata.get("page", 1)
            # Use content directly as chunks already carry clean context
            content = doc.page_content.strip()
            blocks.append(
                f"[Document: {filename} | Page: {page}]\n{content}"
            )
        return "\n\n---\n\n".join(blocks)

    def extract_sources(self, scored_docs: List[Tuple[Document, float]]) -> List[SourceCitation]:
        seen = set()
        citations = []
        for doc, score in scored_docs:
            filename = doc.metadata.get("filename", "document")
            page = int(doc.metadata.get("page", 1))
            key = (filename, page)
            if key in seen:
                continue
            seen.add(key)

            snippet = doc.page_content[:280].strip()
            if len(doc.page_content) > 280:
                snippet += "..."

            image_url = doc.metadata.get("image_url")
            ocr = bool(doc.metadata.get("ocr", False))

            citations.append(
                SourceCitation(
                    filename=filename,
                    page=page,
                    page_label=str(page),
                    snippet=snippet,
                    image_url=image_url,
                    ocr=ocr
                )
            )
        return citations

    async def answer_query(self, query: str, session_id: str = "default") -> ChatQueryResponse:
        try:
            scored_docs = await self.retrieve_context(query, k=10)
        except VectorServiceRateLimitError:
            rate_limit_ans = "The AI embedding service is temporarily rate-limited due to heavy ingestion traffic. Please wait 10 seconds and resend your question."
            return ChatQueryResponse(
                answer=rate_limit_ans,
                is_refusal=False,
                sources=[],
                session_id=session_id
            )
        except Exception as e:
            logger.error(f"Retrieval error: {str(e)}")
            scored_docs = []

        # If no documents retrieved
        if not scored_docs:
            refusal_ans = settings.REFUSAL_STRING
            await mongo_store.save_chat_message(
                session_id=session_id,
                role="user",
                content=query
            )
            await mongo_store.save_chat_message(
                session_id=session_id,
                role="assistant",
                content=refusal_ans,
                is_refusal=True,
                sources=[]
            )
            return ChatQueryResponse(
                answer=refusal_ans,
                is_refusal=True,
                sources=[],
                session_id=session_id
            )

        context_str = self.format_context_blocks(scored_docs)
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context_str)

        try:
            response = self.client.chat.completions.create(
                model=settings.GENERATION_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                temperature=0.0
            )
            raw_answer = response.choices[0].message.content.strip()
        except Exception as e:
            err_str = str(e).lower()
            logger.error(f"Gemini generation failed: {str(e)}")
            if "429" in err_str or "quota" in err_str:
                return ChatQueryResponse(
                    answer="The AI generation service is temporarily busy. Please wait a moment and resend your question.",
                    is_refusal=False,
                    sources=[],
                    session_id=session_id
                )
            raw_answer = settings.REFUSAL_STRING

        # Clean any accidental emojis or unwanted whitespace
        clean_answer = re.sub(r'[\U00010000-\U0010ffff]', '', raw_answer).strip()

        # Check if the model triggered refusal
        is_refusal = (
            settings.REFUSAL_STRING.lower() in clean_answer.lower() or
            "not covered in the provided course materials" in clean_answer.lower() or
            "information is not covered" in clean_answer.lower() or
            "not mentioned in the provided" in clean_answer.lower()
        )

        if is_refusal:
            final_answer = settings.REFUSAL_STRING
            sources = []
        else:
            # Strip inline bracket citations (e.g., [filename.pdf, Page N], [Page N], [Document: ...])
            clean_answer = re.sub(
                r'\s*\[\s*(?:(?:[^\]]*\.(?:pdf|png|jpg|jpeg|webp|md|txt))|(?:Page\s*\d+)|(?:Document:\s*[^\]]+))[^\]]*\]',
                '',
                clean_answer
            )
            clean_answer = re.sub(r' +', ' ', clean_answer)
            clean_answer = re.sub(r'\s+([,\.\?!;:])', r'\1', clean_answer).strip()
            final_answer = clean_answer
            sources = self.extract_sources(scored_docs)

        # Persist conversation in MongoDB
        await mongo_store.save_chat_message(
            session_id=session_id,
            role="user",
            content=query
        )
        await mongo_store.save_chat_message(
            session_id=session_id,
            role="assistant",
            content=final_answer,
            is_refusal=is_refusal,
            sources=[s.model_dump() for s in sources]
        )

        return ChatQueryResponse(
            answer=final_answer,
            is_refusal=is_refusal,
            sources=sources,
            session_id=session_id
        )


rag_service = RagService()
