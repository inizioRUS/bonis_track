from fastapi import FastAPI

from core.dependencies import lifespan
from routers.ingest import router as ingest_router
from routers.search import router as search_router


app = FastAPI(
    title="Retriever Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(ingest_router, prefix="", tags=["ingest"])
app.include_router(search_router, prefix="", tags=["search"])


@app.get("/health")
def health():
    return {"status": "ok"}