import os
from pydantic import BaseModel, Field


class Settings(BaseModel):
    environment: str = os.getenv("ENV", "development")
    api_port: int = int(os.getenv("API_PORT", "8000"))

    mongodb_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    mongodb_db: str = os.getenv("MONGODB_DB", "studyqna")
    mongodb_server_selection_timeout_ms: int = int(
        os.getenv("MONGODB_SERVER_SELECTION_TIMEOUT_MS", "5000")
    )

    faiss_index_dir: str = os.getenv("FAISS_INDEX_DIR", "./data/faiss")
    upload_dir: str = os.getenv("UPLOAD_DIR", "./data/uploads")

    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "local")  # Default to local (sentence-transformers)
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")  # Only used if provider=openai
    embedding_local_model: str = os.getenv(
        "EMBEDDING_LOCAL_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )
    embedding_batch_size: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))

    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini")  # Default to Gemini
    llm_model: str = os.getenv("LLM_MODEL", "gemini-2.5-flash")
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "2048"))  # Increased for Gemini
    rag_max_context_length: int = int(os.getenv("RAG_MAX_CONTEXT_LENGTH", "20000"))  # Max chars in context
    
    # RAG Configuration
    rag_low_similarity_threshold: float = float(os.getenv("RAG_LOW_SIMILARITY_THRESHOLD", "0.4"))
    rag_low_confidence_threshold: float = float(os.getenv("RAG_LOW_CONFIDENCE_THRESHOLD", "0.3"))
    rag_max_context_length_tokens: int = int(os.getenv("RAG_MAX_CONTEXT_LENGTH_TOKENS", "8000"))
    rag_max_references: int = int(os.getenv("RAG_MAX_REFERENCES", "5"))
    admin_emails: set[str] = Field(
        default_factory=lambda: {
            email.strip().lower()
            for email in os.getenv("ADMIN_EMAILS", "").split(",")
            if email.strip()
        }
    )

    # API keys
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY", "AIzaSyDQ0lDuBeMsBdB_Jr7tOsJoVJWPZ9J_nq0")

    # Google Calendar integration
    google_client_id: str | None = os.getenv("GOOGLE_CLIENT_ID")
    google_client_secret: str | None = os.getenv("GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str | None = os.getenv("GOOGLE_REDIRECT_URI")
    calendar_token_secret: str | None = os.getenv("CALENDAR_TOKEN_SECRET")
    calendar_success_redirect: str = os.getenv(
        "CALENDAR_SUCCESS_REDIRECT", "http://localhost:5173/settings?calendar=connected"
    )
    calendar_failure_redirect: str = os.getenv(
        "CALENDAR_FAILURE_REDIRECT", "http://localhost:5173/settings?calendar=error"
    )

    # Auth/JWT
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "dev-secret-change-me")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    # CORS
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv(
                "CORS_ALLOW_ORIGINS",
                ",".join(
                    [
                        # Production (Vercel)
                        "https://studyqna.vercel.app",
                        # Local dev
                        "http://localhost:5173",
                        "http://localhost:3000",
                        "http://127.0.0.1:5173",
                        "http://127.0.0.1:3000",
                    ]
                ),
            ).split(",")
            if origin.strip()
        ]
    )
    # Allows Vercel preview deployments like https://studyqna-git-xyz.vercel.app
    cors_allow_origin_regex: str | None = os.getenv(
        "CORS_ALLOW_ORIGIN_REGEX", r"^https://.*\.vercel\.app$"
    )


settings = Settings()


