"""Unit tests for StateManager deduplication and persistent JSON handling."""

import json
from src.models import Coupon
from src.state_manager import StateManager


def test_state_manager_deduplication(tmp_path):
    """Verify that StateManager filters previously recorded coupons."""
    state_file = tmp_path / "test_state.json"
    manager = StateManager(state_file_path=state_file)

    c1 = Coupon(title="Coupon 1", code="C1")
    c2 = Coupon(title="Coupon 2", code="C2")

    # Initial run: all coupons should be new
    new_coupons = manager.filter_new_coupons([c1, c2])
    assert len(new_coupons) == 2

    # Record c1 as processed
    manager.record_processed([c1])

    # Second run: c1 should be filtered out, only c2 returned
    filtered_coupons = manager.filter_new_coupons([c1, c2])
    assert len(filtered_coupons) == 1
    assert filtered_coupons[0].item_id == c2.item_id

    # Verify JSON structure on disk
    with open(state_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert c1.item_id in data["processed_coupon_ids"]
        assert data["last_run"] is not None
