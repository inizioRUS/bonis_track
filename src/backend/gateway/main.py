from contextlib import asynccontextmanager

from fastapi import FastAPI

from db.postgres.models import Base
from db.postgres.postgres import engine
from gateway.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="PoC RAG Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)