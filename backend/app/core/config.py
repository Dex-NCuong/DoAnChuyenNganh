import os
from pydantic import BaseModel, Field


class Settings(BaseModel):
    environment: str = os.getenv("ENV", "development")
    api_port: int = int(os.getenv("API_PORT", "8000"))

    mongodb_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    mongodb_db: str = os.getenv("MONGODB_DB", "studyqna")

    faiss_index_dir: str = os.getenv("FAISS_INDEX_DIR", "./data/faiss")
    upload_dir: str = os.getenv("UPLOAD_DIR", "./data/uploads")

    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "openai")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_local_model: str = os.getenv(
        "EMBEDDING_LOCAL_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )
    embedding_batch_size: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))

    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini")  # Default to Gemini
    llm_model: str = os.getenv("LLM_MODEL", "gemini-2.5-flash")
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "2048"))  # Increased for Gemini
    rag_max_context_length: int = int(os.getenv("RAG_MAX_CONTEXT_LENGTH", "20000"))  # Max chars in context
    admin_emails: set[str] = Field(
        default_factory=lambda: {
            email.strip().lower()
            for email in os.getenv("ADMIN_EMAILS", "").split(",")
            if email.strip()
        }
    )

    # API keys
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY", "AIzaSyCp9rDco53tJdc7w9zHulbXw1ST666ZuEY")

    # Auth/JWT
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "dev-secret-change-me")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


settings = Settings()


