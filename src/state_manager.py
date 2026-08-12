"""State management and deduplication handler."""

import json
from datetime import datetime, timezone
from pathlib import Path
from src.models import Coupon


class StateManager:
    """Handles persistent idempotency records via local JSON storage."""

    def __init__(self, state_file_path: Path) -> None:
        self.state_file_path = state_file_path

    def _load_state(self) -> dict:
        """Load state JSON object from disk, initializing if missing."""
        if not self.state_file_path.exists():
            return {
                "last_run": None,
                "processed_coupon_ids": [],
            }

        try:
            with open(self.state_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return {"last_run": None, "processed_coupon_ids": []}
                return data
        except (json.JSONDecodeError, OSError):
            return {"last_run": None, "processed_coupon_ids": []}

    def filter_new_coupons(self, coupons: list[Coupon]) -> list[Coupon]:
        """Filter out coupons that have already been processed in previous runs.

        Args:
            coupons: Raw extracted coupons list.

        Returns:
            List of previously unseen Coupon instances.
        """
        state = self._load_state()
        seen_ids = set(state.get("processed_coupon_ids", []))

        new_coupons = [c for c in coupons if c.item_id not in seen_ids]
        return new_coupons

    def record_processed(self, processed_coupons: list[Coupon]) -> None:
        """Update the state file with newly processed coupon IDs and timestamp.

        Args:
            processed_coupons: List of novel coupons that were successfully notified.
        """
        state = self._load_state()
        existing_ids = set(state.get("processed_coupon_ids", []))

        for coupon in processed_coupons:
            existing_ids.add(coupon.item_id)

        state["last_run"] = datetime.now(timezone.utc).isoformat()
        state["processed_coupon_ids"] = sorted(list(existing_ids))

        # Write state atomically
        with open(self.state_file_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
