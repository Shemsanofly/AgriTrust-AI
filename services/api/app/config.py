import socket
from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    app_name: str = "Shambani → Kifedha"
    dev_mode: bool = True

    database_url: str = "sqlite:///./shamba.db"

    jwt_secret: str = "change-me"
    access_token_minutes: int = 30
    refresh_token_days: int = 7

    # Blockchain. When RPC_URL + contract address + signer key are all set and web3 is
    # installed, proofs are written to a real EVM chain. Otherwise a local append-only
    # ledger is used and every proof is labelled SIMULATED.
    rpc_url: str = ""
    chain_id: int = 31337
    anchor_signer_key: str = ""
    evidence_registry_address: str = ""
    receipt_registry_address: str = ""

    # Weather: "live" calls Open-Meteo and falls back to simulated data if offline.
    weather_mode: str = "live"
    open_meteo_base: str = "https://api.open-meteo.com/v1"
    # Place names from GPS: "live" asks OpenStreetMap, "offline" uses the nearest region only.
    geocode_mode: str = "live"

    africastalking_username: str = "sandbox"
    africastalking_api_key: str = ""
    africastalking_ussd_code: str = ""
    africastalking_sender_id: str = ""

    # USSD / SMS channel settings (provider adapters live under app.communication).
    ussd_provider: str = "africastalking"  # africastalking | beem | console
    sms_provider: str = "africastalking"  # africastalking | beem | console
    ussd_enabled: bool = True
    sms_enabled: bool = True
    ussd_session_ttl_minutes: int = 5
    public_base_url: str = ""  # e.g. https://xxxxx.ngrok-free.app — used in docs only

    beem_api_key: str = ""
    beem_secret_key: str = ""
    beem_ussd_code: str = ""
    beem_sender_id: str = ""

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    public_web_url: str = "http://localhost:5173"

    # Passkeys / device biometrics (WebAuthn). RP ID must be the site's host name.
    webauthn_rp_id: str = "localhost"
    webauthn_origins: str = "http://localhost:5173,http://localhost:8080,http://localhost:4173"

    # Face sign-in (FACEIO, https://console.faceio.net). Both empty = feature hidden.
    # The public ID goes to the browser; the API key stays on the server.
    faceio_public_id: str = ""
    faceio_api_key: str = ""

    # Orders above this value (TZS) need PIN step-up confirmation.
    step_up_threshold_tzs: int = 500_000
    max_failed_logins: int = 5
    lockout_minutes: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _lan_ip() -> str | None:
    """This machine's address on the local network (no packets are sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


@lru_cache
def public_web_url() -> str:
    """Base URL printed in QR codes. A localhost PUBLIC_WEB_URL is useless to a phone
    scanning the code, so swap in the LAN address; any real domain is used as-is."""
    url = urlsplit(get_settings().public_web_url.rstrip("/"))
    if url.hostname in ("localhost", "127.0.0.1") and (ip := _lan_ip()):
        return urlunsplit(url._replace(netloc=f"{ip}:{url.port}" if url.port else ip))
    return url.geturl()
