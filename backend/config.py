"""Central configuration for HireWise.

All values can be overridden through environment variables or a local `.env`
file (see `.env.example`).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent          # repository root
BACKEND_DIR = Path(__file__).resolve().parent              # backend/
DATA_DIR = ROOT_DIR / "data"                               # sqlite db
STORAGE_DIR = ROOT_DIR / "storage" / "cvs"                 # encrypted CV files
KB_DOCS_DIR = ROOT_DIR / "knowledge_base" / "docs"         # markdown/json seed docs
CHROMA_DIR = ROOT_DIR / "chroma_db"                        # persistent ChromaDB
FRONTEND_DIR = ROOT_DIR / "frontend"                       # static dashboard
SAMPLES_DIR = ROOT_DIR / "samples"

for _d in (DATA_DIR, STORAGE_DIR, KB_DOCS_DIR, CHROMA_DIR):
    _d.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT_DIR / ".env"), extra="ignore")

    # app
    app_name: str = "HireWise"
    debug: bool = True
    database_url: str = "sqlite:///./data/hirewise.db"

    # security
    secret_key: str = "change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    encryption_key: str = ""                 # Fernet key (32-byte urlsafe base64)

    # upload rules
    max_upload_mb: int = 5
    allowed_extensions: str = "pdf,docx,txt,md"

    # bootstrap admin
    admin_username: str = "admin"
    admin_password: str = "admin123"
    admin_email: str = "admin@hirewise.local"

    # optional LLM (none | gemini | openai | ollama)
    llm_provider: str = "none"               # none = deterministic pipeline only
    google_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    llm_model: str | None = None

    # scoring rubric (Agent 2) -- transparent, fixed weights
    weight_mandatory_skills: float = 0.45
    weight_experience: float = 0.25
    weight_education: float = 0.15
    weight_preferred_skills: float = 0.15

    # Agent 3 thresholds
    extraction_confidence_ok: float = 0.75    # below this -> workflow review
    matching_confidence_ok: float = 0.55
    strong_match_min: float = 80.0
    potential_match_min: float = 65.0
    candidate_id_prefix: str = "CAND"
    kb_collection: str = "hirewise_kb"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def allowed_ext_list(self) -> list[str]:
        return [e.strip().lower() for e in self.allowed_extensions.split(",") if e.strip()]

    @property
    def scoring_weights(self) -> dict[str, float]:
        return {
            "mandatory_skills": self.weight_mandatory_skills,
            "experience": self.weight_experience,
            "education": self.weight_education,
            "preferred_skills": self.weight_preferred_skills,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()