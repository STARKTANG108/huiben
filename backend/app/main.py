from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers.book import router as book_router
from app.routers.projects import router as projects_router
from app.routers.settings import router as settings_router

settings = get_settings()
# Ensure storage exists at boot
settings.storage_path.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Pictale API",
    description="儿童绘本视频 + 书籍剪辑",
    version="0.8.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router)
app.include_router(settings_router)
app.include_router(book_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"name": "pictale", "docs": "/docs"}
