"""Idempotency tests for inbound message de-duplication.

``dedupe.mark_if_new`` must be exactly-once per message id: the first caller
gets True (process it), concurrent/later duplicates get False (skip). It relies
on a DynamoDB conditional write; here we back it with a fake table that enforces
the same attribute_not_exists condition so the logic is tested without AWS.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from shared import dedupe


class _FakeConditionalTable:
    """Minimal DynamoDB stand-in enforcing attribute_not_exists(message_id)."""

    def __init__(self):
        self.items: dict[str, dict] = {}

    def put_item(self, Item, ConditionExpression=None):
        from botocore.exceptions import ClientError
        mid = Item["message_id"]
        if ConditionExpression and mid in self.items:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem")
        self.items[mid] = Item


@pytest.fixture
def table(monkeypatch):
    t = _FakeConditionalTable()
    monkeypatch.setattr(dedupe, "_table", lambda: t)
    return t


def test_first_time_is_new(table):
    assert dedupe.mark_if_new("msg-1") is True


def test_duplicate_is_rejected(table):
    assert dedupe.mark_if_new("msg-1") is True
    assert dedupe.mark_if_new("msg-1") is False
    assert dedupe.mark_if_new("msg-1") is False


def test_distinct_ids_each_new(table):
    assert dedupe.mark_if_new("a") is True
    assert dedupe.mark_if_new("b") is True


def test_missing_id_is_processed_not_dropped(table):
    # An empty id cannot be de-duplicated; process rather than silently drop.
    assert dedupe.mark_if_new("") is True


def test_ttl_attribute_is_set(table):
    dedupe.mark_if_new("msg-ttl")
    item = table.items["msg-ttl"]
    assert "ttl" in item and isinstance(item["ttl"], int)
