"""Unit tests for models and hash generation."""

from src.models import Coupon, IngestionResult, IngestionStatus


def test_coupon_deterministic_hash():
    """Verify that coupon items generate identical SHA-256 hashes for identical properties."""
    c1 = Coupon(title="Evrit Book Code", code="EVR123", expiration_date="2026-09-01")
    c2 = Coupon(title="Evrit Book Code", code="EVR123", expiration_date="2026-09-01")

    assert c1.item_id == c2.item_id
    assert len(c1.item_id) == 16


def test_coupon_different_hashes():
    """Verify that different codes produce distinct hashes."""
    c1 = Coupon(title="Evrit Book Code", code="EVR123")
    c2 = Coupon(title="Evrit Book Code", code="EVR999")

    assert c1.item_id != c2.item_id


def test_ingestion_result_defaults():
    """Verify default status and timestamp presence in IngestionResult."""
    res = IngestionResult(status=IngestionStatus.SUCCESS)
    assert res.status == IngestionStatus.SUCCESS
    assert res.timestamp is not None
    assert res.coupons == []
