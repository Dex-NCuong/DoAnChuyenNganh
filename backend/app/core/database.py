from __future__ import annotations

from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .config import settings


_mongo_client: Optional[AsyncIOMotorClient] = None
_mongo_db: Optional[AsyncIOMotorDatabase] = None


def get_mongo_client() -> AsyncIOMotorClient:
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = AsyncIOMotorClient(settings.mongodb_uri)
    return _mongo_client


def get_database() -> AsyncIOMotorDatabase:
    global _mongo_db
    if _mongo_db is None:
        client = get_mongo_client()
        _mongo_db = client[settings.mongodb_db]
    return _mongo_db


# FAISS utilities (initialized lazily)
def ensure_faiss_index_dir() -> str:
    import os

    os.makedirs(settings.faiss_index_dir, exist_ok=True)
    return settings.faiss_index_dir


def get_faiss_index_path(namespace: str = "default") -> str:
    import os

    ensure_faiss_index_dir()
    sanitized = namespace.replace("/", "_")
    return os.path.join(settings.faiss_index_dir, f"{sanitized}.faiss")


def create_or_load_faiss_index(dimension: int, namespace: str = "default"):
    """Create or load a FAISS index file for the given namespace."""
    import os

    try:
        import faiss  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "FAISS is not available. Please install faiss-cpu/faiss-gpu for your platform."
        ) from exc

    path = get_faiss_index_path(namespace)

    if os.path.exists(path):
        index = faiss.read_index(path)
        if index.d != dimension:
            raise RuntimeError(
                f"Existing FAISS index dimension {index.d} does not match requested {dimension}."
            )
        return index

    base_index = faiss.IndexFlatL2(dimension)
    index = faiss.IndexIDMap(base_index)
    faiss.write_index(index, path)
    return index


def save_faiss_index(index, namespace: str = "default") -> None:
    try:
        import faiss  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "FAISS is not available. Please install faiss-cpu/faiss-gpu for your platform."
        ) from exc

    path = get_faiss_index_path(namespace)
    faiss.write_index(index, path)


