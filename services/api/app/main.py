import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .chain.anchor import chain_mode
from .config import get_settings
from .db import init_db
from .routers import admin, auth, batches, contracts, demo, face, farms, finance, iot, market, sms, ussd, verify, webauthn

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


settings = get_settings()
app = FastAPI(
    title="Shambani → Kifedha API",
    description="Farm → Storage → Market → Finance. Kiswahili + English.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (auth, webauthn, face, farms, iot, batches, market, contracts, verify, finance, admin, demo, ussd, sms):
    app.include_router(module.router)
app.include_router(auth.me_router)
app.include_router(ussd.alias_router)


@app.get("/health")
def health():
    return {"status": "ok", "chain_mode": chain_mode(), "weather_mode": settings.weather_mode, "dev_mode": settings.dev_mode}
