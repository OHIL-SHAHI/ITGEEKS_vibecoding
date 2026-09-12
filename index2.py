import time
import base64
from pathlib import Path
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_qdrant import QdrantVectorStore
import pymupdf


# Load environment variables
load_dotenv()

# PDF path
path = Path(__file__).parent / "unit5dsp.pdf"

# --- Config ---
MIN_CHARS_THRESHOLD = 20   # below this, treat page as "no usable text" -> needs OCR
OCR_MODEL = "gemini-3.5-flash-lite"  # any current Gemini model with vision/image input support
DPI_SCALE = 2.0  # 2.0 ≈ 144 DPI, good balance of legibility vs image size



def render_page_as_base64_png(pdf_path: Path, page_number: int, scale: float = DPI_SCALE) -> str:
    """Render a single PDF page to a PNG and return it as a base64 string."""
    doc = pymupdf.open(pdf_path)
    page = doc[page_number]
    mat = pymupdf.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat)
    png_bytes = pix.tobytes("png")
    doc.close()
    return base64.b64encode(png_bytes).decode("utf-8")


def transcribe_handwritten_page(vlm, image_b64: str) -> str:
    """Send a page image to a vision-capable LLM and get back transcribed text."""
    message = HumanMessage(
        content=[
            {
                "type": "text",
                "text": (
                    "Transcribe all handwritten and printed text on this page exactly "
                    "as written. Preserve structure (headings, bullet points, equations) "
                    "where possible. Do not add commentary, only output the transcription."
                ),
            },
            {
                "type": "image_url",
                "image_url": f"data:image/png;base64,{image_b64}",
            },
        ]
    )
    response = vlm.invoke([message])

    # response.content can be a plain string OR a list of content blocks
    # depending on the model/response — normalize to a single string either way.
    content = response.content
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                text_parts.append(part["text"])
        content = "\n".join(text_parts)

    return content.strip() if isinstance(content, str) else str(content)


# --- Load PDF normally first ---
loader = PyPDFLoader(file_path=path)
docs = loader.load()

# --- Identify pages that need OCR (empty/near-empty text extraction) ---
vlm = ChatGoogleGenerativeAI(model=OCR_MODEL)

for i, doc in enumerate(docs):
    extracted = doc.page_content.strip()
    if len(extracted) < MIN_CHARS_THRESHOLD:
        page_number = doc.metadata.get("page", i)  # PyPDFLoader stores 0-indexed page num
        print(f"Page {page_number}: little/no text found, running OCR...")

        image_b64 = render_page_as_base64_png(path, page_number)
        transcribed_text = transcribe_handwritten_page(vlm, image_b64)

        # Replace the (empty) content with the transcription, keep the same metadata
        doc.page_content = transcribed_text
        doc.metadata["ocr"] = True  # tag it so you know this page went through OCR

# --- From here on, everything is unchanged ---

# Split the documents into chunks
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=400
)

chunks = text_splitter.split_documents(docs)

# Google Gemini embedding model
embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-2"
)

# Throttling settings
batch_size = 20
delay = 15  # seconds

first_batch = chunks[:batch_size]

vector_store = QdrantVectorStore.from_documents(
    documents=first_batch,
    embedding=embeddings,
    url="http://localhost:6333",
    collection_name="rag"
)

# Add remaining batches
for i in range(batch_size, len(chunks), batch_size):
    batch = chunks[i:i + batch_size]
    vector_store.add_documents(batch)
    processed = min(i + batch_size, len(chunks))
    print(f"Processed {processed}/{len(chunks)} chunks")

    if processed < len(chunks):
        print(f"Waiting {delay} seconds...")
        time.sleep(delay)

print("Indexing of documents done!")