import uvicorn

from core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "gateway.main:core",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )
