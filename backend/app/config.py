from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_api_key: str = ""
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "openai/gpt-oss-120b"
    llm_reasoning_effort: str = ""
    llm_temperature: float = 0.3
    llm_timeout_seconds: float = 20.0
    llm_max_completion_tokens: int = 1024
    llm_max_candidates: int = 15

    # Provider limits for openai/gpt-oss-120b on Groq. A value <= 0 disables that check.
    llm_rpm_limit: int = 30
    llm_rpd_limit: int = 1000
    llm_tpm_limit: int = 8000
    llm_tpd_limit: int = 200000
    llm_limit_margin: float = Field(default=0.9, gt=0, le=1)
    llm_usage_db: str = "data/processed/llm_usage.sqlite"

    # Per-client cap on POST /recommendations (each client = one IP address). <= 0 disables it.
    rate_limit_per_minute: int = 10

    cache_ttl_seconds: int = 600
    cache_max_entries: int = 256

    database_path: str = "data/processed/restaurants.sqlite"
    top_k: int = 20
    result_limit: int = 5

    min_candidates: int = 8
    budget_low_max: int = 400
    budget_medium_max: int = 800
    budget_soft_margin: int = 100

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
