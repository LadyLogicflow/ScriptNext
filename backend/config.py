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
    # DEV-Default: "1Admin&BStNext" — vor Prod-Deploy über Env-Var überschreiben
    admin_passwort_hash: str = "$2b$12$bDQBHCWCZDm9zwwhaReG5e3NnYaQYbGTs3BuLFIrO/A3x3LszehHq"

    # CORS — kommagetrennte Origins, kein Wildcard wenn Cookies genutzt werden
    cors_allowed_origins: str = "http://localhost:3000"

    # Embeddings
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # KI (Anthropic)
    anthropic_api_key: str = ""

    # SharePoint / Microsoft Graph
    sharepoint_client_id: str = ""
    sharepoint_authority: str = "common"  # Azure-AD-Tenant-ID oder "common"
    sharepoint_token_key: str = ""        # Fernet-Key für Token-Verschlüsselung (optional)

    # Ingest
    chunk_groesse: int = 500        # Tokens/Wörter pro Chunk
    chunk_overlap: int = 50         # Überlapp zwischen Chunks
    max_upload_mb: int = 50

    model_config = {"env_file": ".env", "env_prefix": "SCRIPTNEXT_"}


settings = Settings()
