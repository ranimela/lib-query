"""Configuration management module for lib-query."""

import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

# Automatically load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)


@dataclass(frozen=True)
class Config:
    """Immutable application settings container loaded from environment variables."""

    library_login_url: str
    library_coupon_url: str
    library_id_number: str
    library_password: str
    ntfy_topic_url: str
    state_file_path: Path

    @classmethod
    def load(cls) -> "Config":
        """Load and validate configuration from environment variables.
        
        Raises:
            ValueError: If required environment variables are missing.
        """
        login_url = os.getenv("LIBRARY_LOGIN_URL")
        coupon_url = os.getenv("LIBRARY_COUPON_URL")
        id_number = os.getenv("LIBRARY_ID_NUMBER")
        password = os.getenv("LIBRARY_PASSWORD")
        ntfy_url = os.getenv("NTFY_TOPIC_URL", "https://ntfy.sh/lib-query-ranimela")

        missing: list[str] = []
        if not login_url:
            missing.append("LIBRARY_LOGIN_URL")
        if not coupon_url:
            missing.append("LIBRARY_COUPON_URL")
        if not id_number:
            missing.append("LIBRARY_ID_NUMBER")
        if not password:
            missing.append("LIBRARY_PASSWORD")

        if missing:
            raise ValueError(f"Missing required configuration variables in .env: {', '.join(missing)}")

        return cls(
            library_login_url=login_url,
            library_coupon_url=coupon_url,
            library_id_number=id_number,
            library_password=password,
            ntfy_topic_url=ntfy_url,
            state_file_path=BASE_DIR / "state.json",
        )
