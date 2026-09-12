import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from backend.app.config import settings
from backend.app.models.schemas import (
    SourceCitation,
    ChatQueryRequest,
    ChatQueryResponse,
    DocumentItem
)
from backend.app.services.rag import rag_service


def test_refusal_string_configuration():
    assert settings.REFUSAL_STRING == "The requested information is not covered in the provided course materials."
    assert "not covered in the provided course materials" in settings.REFUSAL_STRING


def test_source_citation_schema():
    citation = SourceCitation(
        filename="lecture-slides.pdf",
        page=5,
        snippet="Binary search takes O(log n) time.",
        image_url="/api/corpus/pages/doc1/5/image",
        ocr=False
    )
    assert citation.filename == "lecture-slides.pdf"
    assert citation.page == 5
    assert citation.ocr is False


def test_chat_query_request_validation():
    req = ChatQueryRequest(query="What is insertion sort?", session_id="test_session")
    assert req.query == "What is insertion sort?"
    assert req.session_id == "test_session"


def test_chat_query_response_schema():
    resp = ChatQueryResponse(
        answer="Insertion sort best case is O(n). [lecture-slides.pdf, Page 9]",
        is_refusal=False,
        sources=[
            SourceCitation(
                filename="lecture-slides.pdf",
                page=9,
                snippet="Best case O(n)"
            )
        ],
        session_id="session_1"
    )
    assert resp.is_refusal is False
    assert len(resp.sources) == 1
    assert resp.sources[0].page == 9


@pytest.mark.asyncio
async def test_refusal_on_empty_context():
    # When no documents are retrieved, exact refusal must be returned
    resp = await rag_service.answer_query("XYZ123NonExistentTopicRandomString999", session_id="test_refusal")
    assert resp.is_refusal is True
    assert resp.answer == settings.REFUSAL_STRING
    assert len(resp.sources) == 0
