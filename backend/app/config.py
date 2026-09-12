import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    GEMINI_API_KEY: str = ""
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "rag_itgeeks"
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "rag_itgeeks"

    OCR_MODEL: str = "gemini-3.5-flash-lite"
    EMBEDDING_MODEL: str = "gemini-embedding-2"
    GENERATION_MODEL: str = "gemini-3.5-flash-lite"

    MIN_CHARS_THRESHOLD: int = 20
    DPI_SCALE: float = 2.0
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 400
    SIMILARITY_THRESHOLD: float = 0.62

    REFUSAL_STRING: str = (
        "The requested information is not covered in the provided course materials."
    )

    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    UPLOADS_DIR: Path = BASE_DIR / "backend" / "uploads"
    PAGES_DIR: Path = BASE_DIR / "backend" / "uploads" / "pages"
    CORPUS_DIR: Path = BASE_DIR / "corpus"
    BENCHMARK_DIR: Path = BASE_DIR / "benchmark"


settings = Settings()
settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
settings.PAGES_DIR.mkdir(parents=True, exist_ok=True)
