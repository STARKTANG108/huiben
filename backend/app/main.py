from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers.book import router as book_router
from app.routers.custom_book import router as custom_book_router
from app.routers.cut import router as cut_router
from app.routers.life import router as life_router
from app.routers.outfits import router as outfits_router
from app.routers.projects import router as projects_router
from app.routers.settings import router as settings_router
from app.routers.xhs import router as xhs_router

settings = get_settings()
# Ensure storage exists at boot
settings.storage_path.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Pictale API",
    description="绘本视频 + 人生副本 + 书籍剪辑 + 混剪视频 + 儿童定制绘本",
    version="0.7.0",
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
app.include_router(outfits_router)
app.include_router(life_router)
app.include_router(book_router)
app.include_router(custom_book_router)
app.include_router(xhs_router)
app.include_router(cut_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"name": "pictale", "docs": "/docs"}
