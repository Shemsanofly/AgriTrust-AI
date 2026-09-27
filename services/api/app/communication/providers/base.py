from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class USSDRequest:
    session_id: str
    phone_number: str
    text: str
    service_code: str = ""
    network_code: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class USSDResponse:
    message: str
    continue_session: bool = True

    @property
    def body(self) -> str:
        prefix = "CON" if self.continue_session else "END"
        return f"{prefix} {self.message}".strip()


@dataclass
class SMSResult:
    status: str  # SENT | LOGGED | FAILED | PENDING
    provider_message_id: str | None = None
    raw: dict[str, Any] | None = None


class USSDProvider(ABC):
    name: str = "base"

    @abstractmethod
    def parse_request(self, form: dict[str, Any]) -> USSDRequest:
        raise NotImplementedError

    def format_response(self, response: USSDResponse) -> str:
        return response.body

    def media_type(self) -> str:
        return "text/plain"


class SMSProvider(ABC):
    name: str = "base"

    @abstractmethod
    def send(self, phone_number: str, message: str, sender_id: str | None = None) -> SMSResult:
        raise NotImplementedError
