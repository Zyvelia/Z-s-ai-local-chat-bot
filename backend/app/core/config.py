from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://character:local_dev_only_password@localhost:5432/character_chat"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    inference_concurrency: int = 2
    redis_url: str = ""
    inference_lease_seconds: int = 120
    inference_max_waiters: int = 100
    inference_max_context: int = 16384
    inference_max_output: int = 2048
    database_pool_size: int = 10
    database_max_overflow: int = 5
    database_pool_timeout: int = 15
    ollama_cache_ttl_seconds: int = 15
    inference_wait_seconds: int = 20
    jwt_secret: str = "CHANGE_ME_BEFORE_DEPLOYMENT"
    cors_origins: str = "http://localhost:8080"
    environment: str = "development"
    media_storage_dir: str = "./data/media"
    audio_storage_dir: str = "./data/audio"
    voice_service_url: str = "http://localhost:8086"
    voice_internal_token: str = "local-dev-voice-token-change-me"
    voice_ids: str = "default"
    max_voice_clips: int = 100

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
