import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application Settings with .env loading."""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    API_SECRET_KEY: str = "my_secure_telemetry_key_9f8d7e6c5b4a321"
    DATABASE_URL: str = "sqlite:///./data/telemetry.db"
    WORKSPACE_ROOT: str = "D:/SOURCE CODE"
    GITHUB_USERNAME: str = ""
    GITHUB_PAT: str = ""
    HEARTBEAT_TIMEOUT_SECONDS: int = 300

    # Privacy ignore patterns
    SENSITIVE_PATTERNS: list[str] = [
        ".env",
        ".env.local",
        "id_rsa",
        "id_ed25519",
        ".pem",
        ".key",
        "credentials.json",
        "service_account.json",
        "token.json",
        ".pfx",
        ".p12"
    ]

    IGNORED_DIRECTORIES: list[str] = [
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        ".idea",
        ".vscode",
        "dist",
        "build",
        ".next",
        ".nuget"
    ]


settings = Settings()
