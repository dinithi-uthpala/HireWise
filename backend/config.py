"""Central configuration for HireWise (pydantic-settings).

Values are read from environment variables or a local ``.env`` file.
See ``.env.example`` at the repository root for the full list of options.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Project paths (runtime directories are created automatically)
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent          # repository root
DATA_DIR = ROOT_DIR / "data"                               # sqlite db
STORAGE_CVS_DIR = ROOT_DIR / "storage" / "cvs"             # encrypted original CVs
KB_DOCS_DIR = ROOT_DIR / "knowledge_base" / "docs"         # seed documents for ChromaDB
CHROMA_DIR = ROOT_DIR / "chroma_db"                        # persistent vector store

for _dir in (DATA_DIR, STORAGE_CVS_DIR, KB_DOCS_DIR, CHROMA_DIR):
    _dir.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """Application settings.

    Every field can be overridden with an environment variable or a line in
    the repository-root ``.env`` file (see ``.env.example``).
    """

    model_config = SettingsConfigDict(env_file=str(ROOT_DIR / ".env"), extra="ignore")

    # --- app -----------------------------------------------------------------
    app_name: str = "HireWise"
    debug: bool = True
    database_url: str = "sqlite:///./data/hirewise.db"
    cors_origins: str = "http://localhost:8501,http://127.0.0.1:8501"

    # --- security --------------------------------------------------------------
    secret_key: str = "change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    encryption_key: str = ""            # optional Fernet key (32-byte url-safe base64)

    # --- upload rules (used by Agent 1's intake boundary) ----------------------
    max_upload_mb: int = 5
    allowed_extensions: str = "pdf,docx,txt,md"

    # --- default admin (created on startup by the API layer) -------------------
    admin_username: str = "admin"
    admin_password: str = "admin123"
    admin_email: str = "admin@hirewise.local"

    # --- Agent 1: Candidate Intelligence Agent ----------------------------------
    candidate_id_prefix: str = "CAND"
    min_text_chars: int = 200                   # below this the CV is "thin"
    low_confidence_threshold: float = 0.60      # below this -> low_confidence status

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: object) -> object:
        """Treat unrelated environment log-level values as the default."""
        if isinstance(value, str) and value.strip().lower() not in {
            "1", "true", "yes", "on", "0", "false", "no", "off"
        }:
            return True
        return value

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Reject known development credentials when debug is disabled."""
        if not self.debug:
            if self.secret_key == "change-me-to-a-long-random-string":
                raise ValueError("SECRET_KEY must be changed when DEBUG=false")
            if self.admin_password == "admin123":
                raise ValueError("ADMIN_PASSWORD must be changed when DEBUG=false")
            if not self.encryption_key or self.encryption_key.startswith("placeholder"):
                raise ValueError("ENCRYPTION_KEY must be configured when DEBUG=false")
        return self

    # optional LLM enhancement (none | gemini | openai | ollama)
    llm_provider: str = "none"
    google_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    llm_model: str | None = None

    # --- Agent 2 scoring rubric (transparent fixed weights) ---------------------
    weight_mandatory_skills: float = 0.45
    weight_experience: float = 0.25
    weight_education: float = 0.15
    weight_preferred_skills: float = 0.15

    # --- Agent 3 thresholds ------------------------------------------------------
    matching_confidence_ok: float = 0.55
    strong_match_min: float = 80.0
    potential_match_min: float = 60.0

    # --- vector store -------------------------------------------------------------
    kb_collection: str = "hirewise_kb"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def allowed_ext_list(self) -> list[str]:
        return [e.strip().lower() for e in self.allowed_extensions.split(",") if e.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached settings instance."""
    return Settings()