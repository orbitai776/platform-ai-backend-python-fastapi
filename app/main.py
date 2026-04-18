from __future__ import annotations

from fastapi import FastAPI

from app.api.v1.router import router as v1_router


def create_app() -> FastAPI:
    app = FastAPI(title="Sprint02 Multi-turn Slot Filling", version="2.0.0")
    app.include_router(v1_router)

    @app.get("/")
    async def root() -> dict[str, object]:
        return {
            "name": app.title,
            "version": app.version,
            "health": "/health",
            "docs": "/docs",
            "openapi": "/openapi.json",
            "api_prefix": "/api/v1",
        }

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
