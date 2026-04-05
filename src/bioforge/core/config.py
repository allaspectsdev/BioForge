from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "BIOFORGE_", "env_file": ".env", "extra": "ignore"}

    # Database
    database_url: str = "postgresql+asyncpg://bioforge:bioforge@localhost:5432/bioforge"

    # Object Storage (S3/MinIO)
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "bioforge-data"

    # AI / Claude
    anthropic_api_key: str = ""
    default_model: str = "claude-sonnet-4-6"
    agent_max_turns: int = 25
    agent_max_budget_usd: float = 1.0

    # Evo 2 configuration
    evo2_mode: str = "auto"  # auto, local, api, mock
    evo2_model: str = "evo2_7b"  # evo2_1b, evo2_7b, evo2_20b, evo2_40b
    together_api_key: str = ""

    # Structure prediction
    structure_mode: str = "auto"  # auto, boltz, openfold, esmfold, mock

    # Platform
    debug: bool = False
    log_level: str = "INFO"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
