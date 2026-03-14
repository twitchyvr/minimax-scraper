"""Application configuration via environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "sqlite+aiosqlite:///./output/scraper.db"

    # Output
    output_dir: Path = Path("./output")

    # Scraping
    rate_limit_rps: float = 5.0
    max_concurrent: int = 5
    max_retries: int = 3
    user_agent: str = "minimax-scraper/0.1.0 (documentation archiver)"

    # AI (MiniMax M2.5 via OpenAI-compatible API)
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimax.chat/v1"
    minimax_model: str = "MiniMax-M2.5"

    # CORS
    cors_origins: list[str] = ["http://localhost:8080", "http://127.0.0.1:8080"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
