"""Cadence API — main application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import items, connections, snapshots, health, config, navigation

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Construction document reconciliation platform. "
        "Three tables, one triple: (what, when, who says)."
    ),
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router, tags=["health"])
app.include_router(config.router, prefix="/api/v1/config", tags=["config"])
app.include_router(items.router, prefix="/api/v1/items", tags=["items"])
app.include_router(connections.router, prefix="/api/v1/connections", tags=["connections"])
app.include_router(snapshots.router, prefix="/api/v1/snapshots", tags=["snapshots"])
app.include_router(navigation.router, prefix="/api/v1", tags=["navigation"])
