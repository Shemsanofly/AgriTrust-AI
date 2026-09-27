"""Provider-agnostic SMS / USSD communication layer.

Application code calls `send_sms` and the USSD engine; provider-specific HTTP
details stay in `providers/`.
"""

from .sms import send_sms

__all__ = ["send_sms"]
