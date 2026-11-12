"""Read-only local Ollama diagnostics and authenticated model preferences."""
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.security import current_user
from app.models.entities import User, Character, Conversation
from app.providers.ollama import OllamaProvider
from app.services.inference import PRESETS, inference_snapshot, effective_options
from app.api.model_schemas import CharacterModelIn, ConversationModelIn

router = APIRouter(prefix="/api/v1", tags=["Local AI"])

@router.get("/ai/models")
async def models(user: User = Depends(current_user)):
    try:
        return {"models": await OllamaProvider().models()}
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "Ollama model discovery unavailable")

@router.get("/ai/health")
async def health(user: User = Depends(current_user)):
    try:
        status = await OllamaProvider().status()
    except (httpx.HTTPError, ValueError):
        status = {"online": False, "version": None, "loaded_models": None}
    return {**status, "queue": await inference_snapshot(), "presets": PRESETS}

@router.get("/ai/presets")
async def presets(user: User = Depends(current_user)):
    return PRESETS

@router.put("/characters/{character_id}/model")
async def character_model(character_id: str, payload: CharacterModelIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    character = await db.get(Character, character_id)
    if character is None or character.creator_id != user.id:
        raise HTTPException(404, "Character not found")
    if payload.model:
        try:
            await OllamaProvider().ensure_installed(payload.model)
        except ValueError:
            raise HTTPException(422, "Model is not installed on Ollama")
        except httpx.HTTPError:
            raise HTTPException(503, "Ollama is unavailable")
    character.preferred_model = payload.model
    await db.commit()
    return {"preferred_model": character.preferred_model}

@router.put("/conversations/{conversation_id}/inference")
async def conversation_model(conversation_id: str, payload: ConversationModelIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise HTTPException(404, "Conversation not found")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("inference_model"):
        try:
            await OllamaProvider().ensure_installed(changes["inference_model"])
        except ValueError:
            raise HTTPException(422, "Model is not installed on Ollama")
        except httpx.HTTPError:
            raise HTTPException(503, "Ollama is unavailable")
    for name, value in changes.items():
        setattr(conversation, name, value)
    await db.commit()
    character = await db.get(Character, conversation.character_id)
    return {"settings": changes, "effective": effective_options(character, conversation).__dict__}
