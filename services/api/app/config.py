from functools import lru_cache

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

    africastalking_username: str = "sandbox"
    africastalking_api_key: str = ""

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    public_web_url: str = "http://localhost:5173"

    # Orders above this value (TZS) need PIN step-up confirmation.
    step_up_threshold_tzs: int = 500_000
    max_failed_logins: int = 5
    lockout_minutes: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()
