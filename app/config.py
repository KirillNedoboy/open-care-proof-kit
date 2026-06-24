import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    env: str
    data_dir: Path
    reports_dir: Path
    allow_cloud_llm: bool


def get_settings() -> Settings:
    return Settings(
        env=os.getenv("OPENCARE_ENV", "local"),
        data_dir=Path(os.getenv("OPENCARE_DATA_DIR", "data")),
        reports_dir=Path(os.getenv("OPENCARE_REPORTS_DIR", "reports")),
        allow_cloud_llm=os.getenv("OPENCARE_ALLOW_CLOUD_LLM", "false").lower() == "true",
    )
