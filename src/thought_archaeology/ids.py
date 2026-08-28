"""Crockford-base32 ULIDs. No third-party ULID package."""

from __future__ import annotations

import secrets
import threading
import time
from datetime import datetime, timezone

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
CROCKFORD_SET = frozenset(CROCKFORD)
ULID_LENGTH = 26

_lock = threading.Lock()
_last_ms = -1
_last_rand = 0


def now_iso() -> str:
    """UTC timestamp at seconds precision with a trailing Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_ulid() -> str:
    """48-bit Unix-ms time + 80-bit entropy; monotonic within a millisecond."""
    global _last_ms, _last_rand
    ms = int(time.time() * 1000)
    with _lock:
        if ms == _last_ms:
            _last_rand += 1
            if _last_rand >= (1 << 80):
                while int(time.time() * 1000) == _last_ms:
                    time.sleep(0.0001)
                ms = int(time.time() * 1000)
                _last_rand = int.from_bytes(secrets.token_bytes(10), "big")
                _last_ms = ms
            rand = _last_rand
        elif ms > _last_ms:
            rand = int.from_bytes(secrets.token_bytes(10), "big")
            _last_ms = ms
            _last_rand = rand
        else:
            # Clock went backwards: keep monotonicity from last issued value.
            _last_rand += 1
            ms = _last_ms
            rand = _last_rand
        ts = ms
        entropy = rand
    return _encode(ts, entropy)


def parse_ulid(s: str) -> str:
    """Return `s` if it is a 26-char Crockford ULID; else raise ValueError."""
    if not isinstance(s, str) or len(s) != ULID_LENGTH:
        raise ValueError(f"ULID must be {ULID_LENGTH} characters, got {s!r}")
    if any(ch not in CROCKFORD_SET for ch in s):
        raise ValueError(f"ULID has invalid Crockford charset: {s!r}")
    return s


def is_ulid(s: str) -> bool:
    try:
        parse_ulid(s)
        return True
    except ValueError:
        return False


def _encode(ms: int, rand: int) -> str:
    n = ((ms & ((1 << 48) - 1)) << 80) | (rand & ((1 << 80) - 1))
    chars = []
    for _ in range(ULID_LENGTH):
        chars.append(CROCKFORD[n & 31])
        n >>= 5
    return "".join(reversed(chars))
