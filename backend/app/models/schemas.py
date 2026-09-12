from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class SourceCitation(BaseModel):
    filename: str
    page: int
    page_label: Optional[str] = None
    snippet: str
    image_url: Optional[str] = None
    ocr: bool = False


class ChatQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Student examination query")
    session_id: Optional[str] = Field(None, description="Chat session identifier")


class ChatQueryResponse(BaseModel):
    answer: str
    is_refusal: bool
    sources: List[SourceCitation]
    session_id: str


class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: str
    is_refusal: Optional[bool] = False
    sources: Optional[List[SourceCitation]] = None


class DocumentItem(BaseModel):
    doc_id: str
    filename: str
    format: str
    page_count: int
    chunk_count: int
    ocr_pages: int
    created_at: str
    status: Optional[str] = "ready"
    progress: Optional[int] = 100
    status_message: Optional[str] = None
    error_message: Optional[str] = None



class DocumentListResponse(BaseModel):
    documents: List[DocumentItem]
    total_documents: int
    total_pages: int
    total_chunks: int


class BenchmarkQuestionResult(BaseModel):
    id: str
    type: str
    question: str
    must_refuse: bool
    expected_pages: List[Dict[str, Any]]
    actual_pages: List[Dict[str, Any]]
    is_refusal: bool
    refusal_correct: bool
    citation_correct: bool
    passed: bool
    answer: str


class BenchmarkRunResponse(BaseModel):
    run_id: str
    timestamp: str
    total_questions: int
    target_questions: int
    refusal_questions: int
    refusal_accuracy: float
    citation_accuracy: float
    overall_pass_rate: float
    results: List[BenchmarkQuestionResult]
