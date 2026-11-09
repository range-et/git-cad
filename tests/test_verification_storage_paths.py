"""Mutation-driven boundary checks for new nested outputs and UTC timestamps."""

import datetime as dt
import re

from cadgit.store import atomic_write, now


def test_atomic_write_creates_all_missing_output_parents(tmp_path):
    path = tmp_path / "not-created" / "nested" / "result.bin"
    payload = b"complete bytes\x00\xff"
    atomic_write(path, payload, replace=False)
    assert path.read_bytes() == payload
    assert list(path.parent.iterdir()) == [path]


def test_history_timestamp_is_unambiguous_utc_with_microseconds():
    before = dt.datetime.now(dt.timezone.utc)
    value = now()
    after = dt.datetime.now(dt.timezone.utc)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z", value)
    parsed = dt.datetime.fromisoformat(value)
    assert parsed.tzinfo == dt.timezone.utc and before <= parsed <= after
