from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Datenbank
    database_url: str = "postgresql+asyncpg://scriptnext:scriptnext@localhost:5432/scriptnext"
    database_url_sync: str = "postgresql://scriptnext:scriptnext@localhost:5432/scriptnext"

    # JWT
    jwt_secret: str = "dev-secret-REPLACE-IN-PROD"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # Admin (DEV-ONLY — vor Prod-Deploy ersetzen)
    admin_benutzername: str = "admin"
    admin_passwort_hash: str = ""  # gesetzt via env ADMIN_PASSWORT_HASH

    # Embeddings
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # Ingest
    chunk_groesse: int = 500        # Tokens/Wörter pro Chunk
    chunk_overlap: int = 50         # Überlapp zwischen Chunks
    max_upload_mb: int = 50

    model_config = {"env_file": ".env", "env_prefix": "SCRIPTNEXT_"}


settings = Settings()
