"""Private-by-default, bounded and normalized image assets.

No arbitrary URLs, filenames, SVG, animated images or original metadata are served.
"""
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.security import current_user
from app.models.entities import Character, Conversation, MediaAsset, Persona, User

router = APIRouter(prefix="/api/v1/media", tags=["media"])
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 12_000_000
MAX_OWNED_ASSETS = 200
ALLOWED_PURPOSES = {"avatar", "gallery", "background"}
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def normalize_image(raw: bytes) -> bytes:
    """Reject misleading/oversize input; strip EXIF and encode a single PNG frame."""
    if not raw or len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("Image must be between 1 byte and 5 MiB")
    try:
        with Image.open(BytesIO(raw)) as img:
            if img.format not in {"JPEG", "PNG", "WEBP"} or getattr(img, "is_animated", False):
                raise ValueError("Only still JPEG, PNG and WebP images are supported")
            if img.width * img.height > MAX_PIXELS:
                raise ValueError("Image dimensions are too large")
            img.load()
            normalized = ImageOps.exif_transpose(img).convert("RGBA")
            if max(normalized.size) > 2048:
                normalized.thumbnail((2048, 2048))
            output = BytesIO()
            normalized.save(output, format="PNG", optimize=True)
            result = output.getvalue()
            if len(result) > 8 * 1024 * 1024:
                raise ValueError("Processed image is too large")
            return result
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Invalid or unsafe image") from exc


def asset_path(key: str) -> Path:
    # storage_key is server generated, never based on a filename or client input
    return Path(settings.media_storage_dir) / key


def asset_data(asset: MediaAsset) -> dict:
    return {"id": asset.id, "purpose": asset.purpose, "character_id": asset.character_id,
            "conversation_id": asset.conversation_id, "persona_id": asset.persona_id,
            "url": f"/api/v1/media/{asset.id}", "size_bytes": asset.size_bytes}


async def can_read(asset: MediaAsset, user: User, db: AsyncSession) -> bool:
    if asset.owner_id == user.id:
        return True
    if asset.character_id:
        char = await db.get(Character, asset.character_id)
        return bool(char and char.is_public and char.moderation_status == "active")
    return False


async def assert_scope(user: User, db: AsyncSession, purpose: str, character_id: str | None,
                       conversation_id: str | None, persona_id: str | None):
    if sum(x is not None for x in (character_id, conversation_id, persona_id)) != 1:
        raise HTTPException(422, "Choose exactly one media owner")
    if character_id:
        c = await db.get(Character, character_id)
        if not c or c.creator_id != user.id:
            raise HTTPException(404, "Character not found")
        if purpose not in {"avatar", "gallery"}:
            raise HTTPException(422, "Unsupported character media purpose")
    elif conversation_id:
        c = await db.get(Conversation, conversation_id)
        if not c or c.user_id != user.id:
            raise HTTPException(404, "Conversation not found")
        if purpose != "background":
            raise HTTPException(422, "Unsupported conversation media purpose")
    else:
        persona = await db.get(Persona, persona_id)
        if not persona or persona.user_id != user.id:
            raise HTTPException(404, "Persona not found")
        if purpose != "avatar":
            raise HTTPException(422, "Unsupported persona media purpose")


@router.post("", status_code=201)
async def upload_image(file: UploadFile = File(...), purpose: str = Form(...),
                       character_id: str | None = Form(None), conversation_id: str | None = Form(None),
                       persona_id: str | None = Form(None), user: User = Depends(current_user),
                       db: AsyncSession = Depends(get_db)):
    if purpose not in ALLOWED_PURPOSES:
        raise HTTPException(422, "Unsupported image purpose")
    await assert_scope(user, db, purpose, character_id, conversation_id, persona_id)
    from sqlalchemy import func
    count = await db.scalar(select(func.count(MediaAsset.id)).where(MediaAsset.owner_id == user.id))
    if (count or 0) >= MAX_OWNED_ASSETS:
        raise HTTPException(429, "Media library limit reached")
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "Unsupported image content type")
    try:
        raw = await file.read(MAX_UPLOAD_BYTES + 1)
        data = normalize_image(raw)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        await file.close()
    key = f"{uuid4().hex}.png"
    target = asset_path(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive mode prevents accidental overwrite. File lives outside published static paths.
    with target.open("xb") as handle:
        handle.write(data)
    asset = MediaAsset(owner_id=user.id, character_id=character_id, conversation_id=conversation_id,
                       persona_id=persona_id, purpose=purpose, storage_key=key,
                       content_type="image/png", size_bytes=len(data))
    db.add(asset)
    try:
        if purpose == "background" and conversation_id:
            conversation = await db.get(Conversation, conversation_id)
            await db.flush()
            conversation.background_media_id = asset.id
        await db.commit()
    except Exception:
        await db.rollback()
        target.unlink(missing_ok=True)
        raise
    return asset_data(asset)


@router.get("")
async def list_media(character_id: str | None = None, conversation_id: str | None = None,
                     persona_id: str | None = None, user: User = Depends(current_user),
                     db: AsyncSession = Depends(get_db)):
    if sum(x is not None for x in (character_id, conversation_id, persona_id)) != 1:
        raise HTTPException(422, "Specify exactly one scope")
    if character_id:
        char = await db.get(Character, character_id)
        if not char or not (char.creator_id == user.id or (char.is_public and char.moderation_status == "active")):
            raise HTTPException(404, "Character not found")
        condition = MediaAsset.character_id == character_id
    elif conversation_id:
        chat = await db.get(Conversation, conversation_id)
        if not chat or chat.user_id != user.id:
            raise HTTPException(404, "Conversation not found")
        condition = MediaAsset.conversation_id == conversation_id
    else:
        persona = await db.get(Persona, persona_id)
        if not persona or persona.user_id != user.id:
            raise HTTPException(404, "Persona not found")
        condition = MediaAsset.persona_id == persona_id
    assets = (await db.scalars(select(MediaAsset).where(condition).order_by(MediaAsset.created_at.desc()).limit(200))).all()
    return [asset_data(a) for a in assets]


@router.get("/{media_id}")
async def get_media(media_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    asset = await db.get(MediaAsset, media_id)
    if not asset or not await can_read(asset, user, db):
        raise HTTPException(404, "Image not found")
    target = asset_path(asset.storage_key)
    if not target.is_file():
        raise HTTPException(404, "Image missing from storage")
    return FileResponse(target, media_type="image/png", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.delete("/{media_id}", status_code=204)
async def delete_media(media_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    asset = await db.get(MediaAsset, media_id)
    if not asset or asset.owner_id != user.id:
        raise HTTPException(404, "Image not found")
    if asset.conversation_id:
        chat = await db.get(Conversation, asset.conversation_id)
        if chat and chat.background_media_id == asset.id:
            chat.background_media_id = None
    key = asset.storage_key
    await db.delete(asset)
    await db.commit()
    asset_path(key).unlink(missing_ok=True)
