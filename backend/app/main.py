from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.core.config import settings
from app.core.db import engine
from app.models.entities import Base
from app.api.routes import router
from app.api.community import router as community_router
from app.api.models_control import router as model_router
from app.api.admin import router as admin_router
from app.api.media import router as media_router
from app.api.voice import router as voice_router
from app.api.story import router as story_router
from app.core.ratelimit import rate_limit_middleware
from app.core.performance import performance_middleware
from app.core.redis_runtime import get_redis, close_redis
from app.api.performance import router as performance_router
from app.api.offline_sync import router as offline_sync_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.environment == "production" and settings.jwt_secret == "CHANGE_ME_BEFORE_DEPLOYMENT":
        raise RuntimeError("Set JWT_SECRET before production deployment")
    if settings.environment == "production" and not settings.redis_url:
        raise RuntimeError("Production requires REDIS_URL for shared rate limits and inference admission")
    if settings.redis_url:
        await get_redis().ping()  # require coordination service on startup
    # Bootstrap convenience ONLY: use Alembic migrations for deployed environments.
    if settings.environment != "production":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    # Production requires a verified, externally applied migration sequence.
    yield
    await close_redis()
    await engine.dispose()

app = FastAPI(title="Character Chat API", version="1.8.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.middleware("http")(performance_middleware)
app.middleware("http")(rate_limit_middleware)
app.include_router(performance_router)
app.include_router(offline_sync_router)
app.include_router(media_router)
app.include_router(voice_router)
app.include_router(story_router)
app.include_router(admin_router)
app.include_router(community_router)  # register /characters/discover before generic /characters/{id}
app.include_router(model_router)
app.include_router(router)

@app.get("/health")
async def health():
    return {"status": "ok"}
