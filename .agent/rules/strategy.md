---
trigger: always_on
---

# strategy.md: Exam-Night Multimodal RAG Study Companion

## 1. Project Overview & Business Requirements
Build an exam-night multimodal RAG assistant designed to answer student queries strictly from ingested course materials. 

### Core Business Constraints
- **Strict Grounding with Page Citations**: Answers must cite the exact file name and page number so the user can verify the original context.
- **Strict Refusal of Out-of-Corpus Questions**: If the course materials do not contain the answer, the system must refuse to answer. Parametric hallucination is treated as a critical failure.
- **Support for Messy Handwriting & Visual Documents**: Ingestion must support lecture PDFs, slides, Markdown/text, and photographed handwritten pages (including poor lighting, skewed angles, formulas, and diagrams).
- **Multi-Document Synthesis**: The pipeline must handle queries that require combining evidence across two or more separate documents.
- **Evaluation Baseline**:
  - Corpus: Minimum 60 pages across 4+ formats (PDF, slides, text/markdown, 2+ handwritten scans).
  - Test set: 20 target questions (10 single-source, 10 multi-source) with verified page citations.
  - Refusal set: 10 syllabus-derived questions not covered in the documents. Target: 100% refusal rate.

---

## 2. Tech Stack
- **Backend**: Python 3.11+, FastAPI, Uvicorn
- **Frontend**: React (Vite, Tailwind CSS, Lucide-React)
- **Vector Database**: Qdrant (HTTP endpoint at `http://localhost:6333`, collection name: `rag_itgeeks`)
- **Metadata Database**: MongoDB (storing chat sessions, evaluation runs, and chunk ingestion logs)
- **Embeddings**: LangChain Google Generative AI Embeddings (`gemini-embedding-2`)
- **VLM & Generation**: Gemini 3.5 Flash Lite via OpenAI-compatible endpoint / LangChain (`ChatGoogleGenerativeAI`)
- **PDF & Visual Extraction**: PyMuPDF (`pymupdf`), `PyPDFLoader`

---

## 3. General Development Guidelines
- Keep it simple, deterministic, and modular. Do not introduce unnecessary abstractions.
- Zero emojis across code, logs, API responses, and user interface.
- No conversational filler or ungrounded generative prose in RAG responses.
- Explicit error handling for Qdrant connections, VLM rate limits, and missing OCR artifacts.
- Test everything against the standard testing tools
- Do not ask for permissions again and again and work in YOLO mode
## Autonomous Execution Policy & Operational Guardrails

### Autonomy Directives
- **Zero-Interruption Execution**: Do not pause to ask for confirmation, clarification, or permission for routine operational tasks. Make sound technical assumptions aligned with the specification, document them in commit logs/code comments, and proceed immediately.
- **Proactive Implementation**: When instructed to implement a feature, generate full, runnable code. Do not output placeholders, omitted sections, `// TODO`, or skeletal code. Implement complete error handling, validation, and typing out of the box.
- **Automatic Environment Self-Correction**: If a tool, script, test, or dependency installation fails, diagnose the error trace, apply the fix, and re-execute autonomously before yielding control.
- **Permitted Interactive Interrupts**: Pause for human approval ONLY if:
  1. An action involves irreversible data destruction (e.g., dropping a production database or clearing uncommitted Git history).
  2. Required third-party credentials (API keys, secrets) are completely absent from the environment and cannot be stubbed.

### Production Engineering Standards
- **Strict Typing and Validation**: All backend endpoints must implement Pydantic v2 schemas for request and response contracts.
- **Deterministic RAG Grounding**: Never allow free-form fallbacks. If the context does not satisfy the similarity threshold or lack explicit evidence, return the exact refusal string.
- **Defensive Error Handling**: Wrap all third-party external I/O (Qdrant client calls, Gemini API, PyMuPDF rendering) in structured `try-except` blocks with typed HTTP exceptions and clean logging.
- **Code Quality**: Enforce clean module separation: Keep routes, vector search services, multimodal parsers, and configuration decoupled. Avoid global mutable state.

---

## 4. RAG Pipeline Specification (Existing Pipeline)

The system relies on the following two core scripts for indexing and retrieval:

### 4.1. Ingestion & Vision-Assisted Parsing (`index2.py`)
- **Page Inspection**: Iterate over PDF pages using `PyPDFLoader`.
- **OCR Trigger**: If page text length is below `MIN_CHARS_THRESHOLD = 20`, trigger vision processing.
- **Vision Extraction**:
  - Render page to PNG using `pymupdf` with `DPI_SCALE = 2.0`.
  - Base64-encode image and dispatch to `ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")`.
  - Transcription Prompt:
    ```text
    Transcribe all handwritten and printed text on this page exactly as written. Preserve structure (headings, bullet points, equations) where possible. Do not add commentary, only output the transcription.
    ```
  - Mark chunk metadata with `ocr: true` and preserve original `page` index.
- **Chunking**: `RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=400)`.
- **Vector Indexing**:
  - Embeddings: `GoogleGenerativeAIEmbeddings(model="gemini-embedding-2")`.
  - Storage: `QdrantVectorStore` targeting collection `rag`.
  - Batching: Throttled at 20 chunks per batch with a 15-second delay to respect rate limits.

### 4.2. Retrieval & Generation Pipeline (`chat.py`)
- **Vector Lookup**: Query `QdrantVectorStore` on collection `rag` using `similarity_search`.
- **Context Construction**:
  ```text
  Page Content: {result.page_content}
  Page Number: {result.metadata['page_label']}
  File location: {result.metadata['source']}