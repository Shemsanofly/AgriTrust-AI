"""Normalize Tanzanian MSISDNs for lookup against User.phone (+255...)."""

from .exceptions import InvalidPhoneError


def normalize_phone(raw: str | None, default_country: str = "255") -> str:
    if raw is None:
        raise InvalidPhoneError("missing_phone")
    digits = "".join(ch for ch in str(raw).strip() if ch.isdigit())
    if not digits:
        raise InvalidPhoneError("invalid_phone")
    if digits.startswith("0") and len(digits) == 10:
        digits = default_country + digits[1:]
    elif len(digits) == 9 and digits.startswith("7"):
        digits = default_country + digits
    elif digits.startswith("00"):
        digits = digits[2:]
    if len(digits) < 10 or len(digits) > 15:
        raise InvalidPhoneError("invalid_phone")
    return f"+{digits}"


def mask_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 6:
        return "***"
    return f"{digits[:4]}******{digits[-2:]}"
