"""Application module."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.deps import DepsContainer
from app.api.routers import users_router, items_router


def create_app() -> FastAPI:
    deps = DepsContainer()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await deps.init_resources()
        db = await deps.db()
        await db.create_all()
        yield
        await deps.shutdown_resources()

    app = FastAPI(
        lifespan=lifespan
    )
    app.deps = deps

    app.include_router(users_router)
    app.include_router(items_router)
    return app

app = create_app()