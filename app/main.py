from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import Base, engine
import app.models  # noqa: F401 — registers all models with Base.metadata
from app.routers import customers_router, campaigns_router, calls_router, webhooks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.include_router(customers_router)
app.include_router(campaigns_router)
app.include_router(calls_router)
app.include_router(webhooks_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "version": settings.app_version}