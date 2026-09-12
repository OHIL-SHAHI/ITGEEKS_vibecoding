import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.services.vector_store import vector_service
from backend.app.services.mongo_store import mongo_store
from backend.app.routes import chat, corpus, benchmark

# Configure standard logging (zero emojis)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("rag_backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Exam-Night Multimodal RAG Backend...")
    # Verify Qdrant connection
    try:
        vector_service.ensure_collection()
        logger.info(f"Qdrant connected. Collection: {settings.QDRANT_COLLECTION}")
    except Exception as e:
        logger.warning(f"Could not connect to Qdrant at startup: {str(e)}")

    # Verify MongoDB connection
    try:
        ping_ok = await mongo_store.ping()
        if ping_ok:
            logger.info(f"MongoDB connected: {settings.MONGODB_DB_NAME}")
        else:
            logger.warning("MongoDB ping failed.")
    except Exception as e:
        logger.warning(f"Could not connect to MongoDB at startup: {str(e)}")

    yield

    logger.info("Shutting down Exam-Night Multimodal RAG Backend...")


app = FastAPI(
    title="Exam-Night Multimodal RAG Companion API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router)
app.include_router(corpus.router)
app.include_router(benchmark.router)


@app.get("/api/health")
async def health_check():
    mongo_ok = await mongo_store.ping()
    return {
        "status": "healthy",
        "service": "rag_backend",
        "qdrant_url": settings.QDRANT_URL,
        "qdrant_collection": settings.QDRANT_COLLECTION,
        "mongodb_connected": mongo_ok
    }
