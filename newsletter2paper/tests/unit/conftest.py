"""Shared fakes for router/unit tests."""
from unittest.mock import MagicMock

import pytest


class FakeSupabase:
    """Minimal stand-in for the Supabase query builder.

    Records every call as (table, op, payload, filters) and returns canned rows per
    (table, op). Unconfigured operations return no rows.
    """

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []
        self.client = MagicMock()
        self.client.table.side_effect = self._table

    def _table(self, name):
        return _Query(self, name)

    def calls_for(self, table, op=None):
        return [c for c in self.calls if c[0] == table and (op is None or c[1] == op)]


class _Query:
    def __init__(self, fake, table):
        self.fake, self.table, self.op, self.payload, self.filters = fake, table, "select", None, []

    def select(self, *_a, **_k):
        self.op = "select"
        return self

    def insert(self, payload):
        self.op, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, col, val):
        self.filters.append((col, val))
        return self

    def execute(self):
        self.fake.calls.append((self.table, self.op, self.payload, tuple(self.filters)))
        rows = self.fake.responses.get((self.table, self.op), [])
        return MagicMock(data=rows)


@pytest.fixture
def fake_supabase():
    return FakeSupabase
