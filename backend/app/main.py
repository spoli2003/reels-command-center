from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import app.models  # noqa: F401
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.reels import router as reels_router
from app.api.youtube import router as youtube_router
from app.api.youtube_analytics import router as youtube_analytics_router
from app.api.youtube_comments import router as youtube_comments_router
from app.api.content import router as content_router
from app.core.config import get_settings
from app.services import youtube_scheduler

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    youtube_scheduler.start()
    yield
    await youtube_scheduler.stop()


app = FastAPI(title=settings.app_name, version="7.0.0-community-inbox", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, same_site="lax", https_only=False)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(reels_router)
app.include_router(youtube_router)
app.include_router(youtube_analytics_router)
app.include_router(youtube_comments_router)

app.include_router(content_router)
