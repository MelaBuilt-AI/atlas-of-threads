from __future__ import annotations

import time

import pytest

from thought_archaeology.ids import CROCKFORD, CROCKFORD_SET, new_ulid, parse_ulid


def test_length_and_charset():
    u = new_ulid()
    assert len(u) == 26
    assert all(ch in CROCKFORD_SET for ch in u)
    parse_ulid(u)


def test_parse_ulid_rejects_bad_length():
    with pytest.raises(ValueError):
        parse_ulid("short")
    with pytest.raises(ValueError):
        parse_ulid("A" * 25)
    with pytest.raises(ValueError):
        parse_ulid("A" * 27)


def test_parse_ulid_rejects_bad_charset():
    bad = "I" + "0" * 25  # I is not Crockford
    with pytest.raises(ValueError):
        parse_ulid(bad)
    with pytest.raises(ValueError):
        parse_ulid("O" * 26)
    with pytest.raises(ValueError):
        parse_ulid("U" * 26)
    with pytest.raises(ValueError):
        parse_ulid("L" * 26)


def test_crockford_alphabet():
    assert CROCKFORD == "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    assert "I" not in CROCKFORD
    assert "L" not in CROCKFORD
    assert "O" not in CROCKFORD
    assert "U" not in CROCKFORD


def test_sort_order_equals_time_order():
    a = new_ulid()
    time.sleep(0.002)
    b = new_ulid()
    assert a < b
    assert sorted([b, a]) == [a, b]


def test_monotonic_in_process():
    ids = [new_ulid() for _ in range(200)]
    assert ids == sorted(ids)
    assert len(set(ids)) == 200
