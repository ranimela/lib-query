"""Data transfer objects and models for lib-query."""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class IngestionStatus(str, Enum):
    """Execution status for the scraping engine."""

    SUCCESS = "SUCCESS"
    AUTH_FAILED = "AUTH_FAILED"
    WAF_BLOCKED = "WAF_BLOCKED"
    DOM_MUTATED = "DOM_MUTATED"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


@dataclass(frozen=True)
class Coupon:
    """Immutable representation of a digital coupon."""

    title: str
    code: str
    description: str = ""
    expiration_date: str = ""
    link: str = ""
    item_id: str = field(init=False)

    def __post_init__(self) -> None:
        """Compute a deterministic unique SHA-256 hash for deduplication."""
        raw_identity = f"{self.title.strip()}|{self.code.strip()}|{self.expiration_date.strip()}"
        computed_id = hashlib.sha256(raw_identity.encode("utf-8")).hexdigest()[:16]
        # Store in dataclass field via object.__setattr__ due to frozen=True
        object.__setattr__(self, "item_id", computed_id)


@dataclass(frozen=True)
class IngestionResult:
    """Output contract produced by the Scraper module."""

    status: IngestionStatus
    coupons: list[Coupon] = field(default_factory=list)
    error_message: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
