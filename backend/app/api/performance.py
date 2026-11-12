"""Admin-only operational metrics; avoids exposing Redis keys to users."""
from fastapi import APIRouter, Depends, HTTPException
from app.api.admin import require_admin
from app.core.redis_runtime import get_redis
from app.services.inference import inference_snapshot
from app.models.entities import User

router = APIRouter(prefix='/api/v1', tags=['operations'])

@router.get('/admin/performance')
async def performance(admin: User = Depends(require_admin)):
    redis = get_redis()
    if redis is None:
        return {'redis': 'disabled', 'queue': await inference_snapshot(), 'api': {}}
    try:
        stats = await redis.hgetall('cc:metrics:api')
    except Exception as exc:
        raise HTTPException(503, 'Metrics store unavailable') from exc
    return {'redis': 'online', 'queue': await inference_snapshot(),
            'api': {key: int(value) for key, value in stats.items()}}
