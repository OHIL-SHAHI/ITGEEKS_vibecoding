# VibeStudy: Exam-Night Multimodal RAG Study Companion

VibeStudy is an exam-night multimodal Retrieval-Augmented Generation (RAG) assistant designed to answer student questions strictly from ingested course materials. It eliminates generative hallucination by enforcing exact page-level citations and strictly refusing to answer any question not supported by the uploaded lecture slides, notes, or handwritten scans.

---

## Key Features

- **Strict Grounding with Exact Page Citations**  
  Every answer is derived directly from ingested documents and accompanied by verified citation chips displaying the source filename and page number.

- **Zero-Tolerance Refusal of Out-of-Corpus Questions**  
  If course materials do not contain the answer, the system returns a standard refusal string:  
  `"The requested information is not covered in the provided course materials."`  
  Parametric hallucinations are treated as critical failures.

- **Multimodal OCR for Messy Handwriting and Visual Scans**  
  Pages with little or no extractable text (below a 20-character threshold) automatically trigger vision extraction. Pages are rendered at 2.0x DPI using PyMuPDF and transcribed using Gemini 3.5 Flash Lite before chunking and embedding.

- **Multi-Document Synthesis**  
  Capable of aggregating evidence across multiple separate documents (for example, combining grading criteria from a syllabus PDF with handwritten algorithm time complexity notes).

- **Interactive Page Inspector**  
  Clicking any citation chip opens a slide-out Page Inspector that renders the exact scanned document page alongside the retrieved context excerpt, complete with zoom controls (60% to 250%).

- **Asynchronous Ingestion with Dynamic Quota Handling**  
  Uploading large documents triggers asynchronous processing in the background. Real-time progress is polled via a dedicated endpoint. The embedding worker dynamically extracts retry delays from Google 429 quota errors and handles up to 8 exponential retries, safely absorbing rate limits.

- **Integrated 30-Question Benchmark Suite**  
  Includes an automated evaluation harness testing 20 target questions (10 single-source and 10 multi-source) and 10 out-of-corpus refusal questions, evaluating answer accuracy, citation correctness, and refusal compliance.

- **Clean Answer Formatting**  
  Inline bracketed citations (such as `[file.pdf, Page 1]`) are removed from response prose and provided as structured metadata chips to keep the answer text clean and easy to read.

---

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn
- **Frontend**: React 19, Vite, Tailwind CSS, Lucide Icons
- **Vector Database**: Qdrant (`rag_itgeeks` collection, 768-dimensional embeddings via cosine similarity)
- **Metadata Database**: MongoDB (stores chat histories, document status, chunk logs, and benchmark runs)
- **Embeddings**: Google Generative AI Embeddings (`gemini-embedding-2`) via LangChain
- **Vision Extraction & Generation**: Google Gemini 3.5 Flash Lite
- **Document Processing**: PyMuPDF (`pymupdf`), `PyPDFLoader`, `RecursiveCharacterTextSplitter`
- **Containerization**: Docker Compose (Qdrant and MongoDB)

---

## Repository Structure

```text
ITGEEKS_vibe_final/
├── .agent/
│   └── rules/
│       └── strategy.md               # Core engineering rules, grounding constraints, zero-emoji policy
├── backend/
│   ├── app/
│   │   ├── models/
│   │   │   └── schemas.py            # Pydantic v2 data models for requests, responses, and citations
│   │   ├── routes/
│   │   │   ├── benchmark.py          # Benchmark trigger and latest result endpoints
│   │   │   ├── chat.py               # Chat query and session management endpoints
│   │   │   └── corpus.py             # Document upload, status polling, deletion, and page rendering
│   │   ├── services/
│   │   │   ├── evaluator.py          # Benchmark test harness and scoring logic
│   │   │   ├── ingestion.py          # Multimodal ingestion, PyMuPDF page rendering, OCR transcription
│   │   │   ├── mongo_store.py        # MongoDB async client for chat sessions and document tracking
│   │   │   ├── rag.py                # Retrieval pipeline, system prompt, refusal detector, source extractor
│   │   │   └── vector_store.py       # Qdrant client, throttled batch indexing, dynamic 429 backoff
│   │   ├── config.py                 # System settings, directory paths, and thresholds
│   │   └── main.py                   # FastAPI application initialization, CORS, and routing
│   └── uploads/                      # Local storage for uploaded files and rendered page images
├── benchmark/
│   └── benchmark_questions.json      # 30-question evaluation dataset (20 target, 10 refusal)
├── corpus/                           # Baseline course materials (handwritten notes, slides, syllabus)
├── frontend/
│   ├── src/
│   │   ├── App.jsx                   # Single-page interface (Chat, Corpus Manager, Benchmark tabs)
│   │   ├── App.css                   # Component styles and transitions
│   │   ├── index.css                 # Base Tailwind CSS directives
│   │   └── main.jsx                  # React application entry point
│   ├── package.json
│   └── vite.config.js
├── scripts/
│   ├── ingest_corpus.py              # CLI utility to index all baseline documents in corpus/
│   └── run_benchmark.py              # CLI utility to execute the 30-question benchmark
├── tests/
│   └── test_rag.py                   # Automated unit and integration tests
├── docker-compose.yml                # Qdrant and MongoDB container definitions
├── requirements.txt                  # Python dependencies
├── start.ps1                         # One-click Windows PowerShell startup script
└── README.md
```

---

## How It Works

### 1. Ingestion and Vision-Assisted Parsing
1. **Format Handling**: Accepts PDF, Markdown, text, PNG, JPG, JPEG, and WebP files.
2. **OCR Trigger**: For PDF pages, PyPDFLoader checks text length. If a page contains fewer than 20 characters (`MIN_CHARS_THRESHOLD`), the system treats it as a scanned or handwritten page.
3. **High-DPI Vision Transcription**:
   - PyMuPDF renders the page to a PNG at 2.0x scale (`DPI_SCALE = 2.0`).
   - The image is encoded to base64 and sent to Gemini 3.5 Flash Lite with a strict transcription prompt to extract all handwritten equations, text, and structural markings.
   - Metadata is tagged with `ocr: true` and the original 1-based page number.
4. **Chunking**: Text is split using `RecursiveCharacterTextSplitter` with `chunk_size=1000` and `chunk_overlap=400`.
5. **Throttled Vector Indexing**:
   - Embeddings are generated using `gemini-embedding-2` in batches of 35 chunks.
   - If Google returns an HTTP 429 quota error, the system inspects the error message, extracts the recommended wait time, pauses accordingly, and retries up to 8 times with exponential backoff.
   - Points are upserted into Qdrant collection `rag_itgeeks`.

### 2. Retrieval and Answer Generation
1. **Vector Lookup**: The user's query is converted to a vector embedding and searched against Qdrant using cosine similarity.
2. **Threshold Gate**: If no retrieved document passes the similarity threshold (`SIMILARITY_THRESHOLD = 0.62`), the system immediately refuses without calling the generation model.
3. **Strict Grounding Prompt**: Retrieved passages are assembled into structured context blocks including document filename and page number.
4. **Generation**: Gemini 3.5 Flash Lite generates the answer at `temperature=0.0`.
5. **Post-Processing**:
   - Inline bracket citations are removed from the answer prose.
   - Exact source references are formatted into structured `SourceCitation` objects.
   - If the model expresses that the answer is not in the text, the response is normalized to the canonical refusal string.

---

## Prerequisites

Before running the project, make sure the following are installed:

- **Docker Desktop** (for running Qdrant and MongoDB)
- **Python 3.11 or higher**
- **Node.js 18 or higher** and `npm`
- **Google Gemini API Key**

---

## Environment Setup

Create a `.env` file in the root directory:

```env
GEMINI_API_KEY=your_gemini_api_key_here
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=rag_itgeeks
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=rag_itgeeks
```

---

## Quick Start

### Option A: Using the PowerShell Startup Script (Windows)

Run the included automated launch script:

```powershell
.\start.ps1
```

This script will:
1. Start Qdrant and MongoDB containers via Docker Compose.
2. Verify that Qdrant is accepting connections.
3. Launch the FastAPI backend on `http://127.0.0.1:8000`.
4. Launch the React + Vite frontend on `http://localhost:5173`.
5. Open your default web browser to the application interface.

---

### Option B: Manual Step-by-Step Startup

#### 1. Start Infrastructure Containers
```bash
docker compose up -d
```
Verify that Qdrant is available at `http://localhost:6333` and MongoDB is available at `localhost:27017`.

#### 2. Install Python Dependencies
```bash
# Create and activate virtual environment
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
```

#### 3. Ingest Baseline Course Materials
Index the sample course documents in `corpus/` into Qdrant:
```bash
python scripts/ingest_corpus.py
```

#### 4. Start Backend Server
```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### 5. Start Frontend Development Server
In a separate terminal:
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Application Views

The user interface is organized into three primary sections:

1. **Companion (Chat View)**  
   - Conversational question-answering grounded in the course materials.
   - Color-coded source citations displaying document name, page number, and OCR indicator.
   - Clickable citation cards open the slide-out Page Inspector with visual scans and zoom controls.
   - Refusal badges indicate when a question falls outside the uploaded syllabus.

2. **Course Corpus Manager**  
   - Summary cards displaying total documents, pages indexed, and OCR status.
   - Searchable document table with status badges (`ready`, `processing`, `failed`).
   - Document upload modal with real-time percentage progress and stage updates.
   - Document deletion with automatic removal of chunks from Qdrant and metadata from MongoDB.

3. **Benchmark Suite**  
   - Real-time execution of the 30-question evaluation dataset.
   - Summary statistics for Groundedness Accuracy, Citation Accuracy, and Out-of-Corpus Refusal Rate.
   - Filterable results table showing each question, retrieved context, generated answer, and validation status.

---

## API Reference

### Chat Endpoints
- `POST /api/chat/query`: Submit a query. Returns answer, refusal flag, source citations, and session ID.
- `GET /api/chat/history/{session_id}`: Retrieve message history for a chat session.

### Corpus Management Endpoints
- `GET /api/corpus/documents`: List all tracked documents in the corpus.
- `POST /api/corpus/upload`: Upload a new file (`multipart/form-data`). Ingestion runs asynchronously in the background.
- `GET /api/corpus/status/{doc_id}`: Poll processing progress and status for an uploaded document.
- `DELETE /api/corpus/documents/{doc_id}`: Remove document metadata, delete associated vectors from Qdrant, and delete cached page scans.
- `GET /api/corpus/pages/{doc_id}/{page_num}`: Serve the rendered PNG image of a specific document page.

### Benchmark Endpoints
- `POST /api/benchmark/run`: Execute the 30-question benchmark evaluation synchronously.
- `GET /api/benchmark/latest`: Retrieve the most recent benchmark run results from MongoDB.

### Health Check
- `GET /api/health`: Verify service connectivity (Qdrant collection status and MongoDB connection).

---

## Testing and Evaluation

### Running Automated Unit Tests
```bash
pytest tests/test_rag.py -v
```

### Running the Evaluation Benchmark via CLI
```bash
python scripts/run_benchmark.py
```

### Target Evaluation Metrics
- **Target Questions**: Minimum 90% groundedness and exact page citation accuracy across single-source and multi-source questions.
- **Refusal Questions**: 100% refusal rate for out-of-corpus or syllabus-derived topics not present in the ingested texts.

---

## Design and Operational Guidelines

- **Zero Emojis**: In accordance with the system specification, no emojis are used across code, terminal logs, API payloads, documentation, or the user interface.
- **Grounded Verification**: Answers must always be traceable back to exact page numbers.
- **Defensive Error Handling**: External service operations (Qdrant, Gemini, PyMuPDF) are wrapped in structured exception blocks with clean error logging and automatic retries.
