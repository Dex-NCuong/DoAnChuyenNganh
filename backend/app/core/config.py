import os
from pydantic import BaseModel


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

    # OpenAI or other provider keys can be added in later modules
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")

    # Auth/JWT
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "dev-secret-change-me")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


settings = Settings()


