"""Canonical JSON, salted keccak256 hashes and Merkle roots (README §9)."""

import json
import secrets
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from Crypto.Hash import keccak


def new_salt() -> str:
    return secrets.token_hex(16)


def keccak256(data: bytes) -> bytes:
    h = keccak.new(digest_bits=256)
    h.update(data)
    return h.digest()


def _normalise(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _normalise(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise(v) for v in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float, Decimal)):
        # Fixed number format so 2500, 2500.0 and 2500.000 hash identically.
        return f"{float(value):.3f}"
    if isinstance(value, datetime):
        return value.replace(microsecond=0).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def canonical_json(record: dict[str, Any]) -> bytes:
    return json.dumps(_normalise(record), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def record_hash(record: dict[str, Any], salt: str) -> str:
    return "0x" + keccak256(canonical_json(record) + bytes.fromhex(salt)).hex()


def record_key(entity_type: str, entity_id: str) -> str:
    """bytes32 id used on chain; derived from public IDs only (no personal data)."""
    return "0x" + keccak256(f"{entity_type}:{entity_id}".encode()).hex()


def merkle_root(leaves: list[bytes]) -> str:
    if not leaves:
        return "0x" + "00" * 32
    level = [keccak256(leaf) for leaf in leaves]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [keccak256(min(a, b) + max(a, b)) for a, b in zip(level[0::2], level[1::2])]
    return "0x" + level[0].hex()
