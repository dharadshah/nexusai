from app.routers.customers import router as customers_router
from app.routers.campaigns import router as campaigns_router
from app.routers.calls import router as calls_router
from app.routers.webhooks import router as webhooks_router

__all__ = ["customers_router", "campaigns_router", "calls_router", "webhooks_router"]