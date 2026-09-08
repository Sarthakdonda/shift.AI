from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / '.env', extra='ignore')
    gemini_api_key: str = ''
    gemini_model: str = 'gemini-2.5-flash'
    mongodb_uri: str = ''
    mongodb_database: str = 'shift_ai'
    cors_origins: str = 'http://localhost:3000'
    max_upload_mb: int = 15
    google_client_id: str = ''
    session_secret: str = ''
    cookie_secure: bool = False
    allow_local_access: bool = True
    vector_search_enabled: bool = False
    vector_index_name: str = 'document_embeddings'
    embedding_model: str = 'gemini-embedding-001'

    @property
    def origins(self):
        return [s.strip() for s in self.cors_origins.split(',') if s.strip()]


@lru_cache
def get_settings():
    return Settings()
