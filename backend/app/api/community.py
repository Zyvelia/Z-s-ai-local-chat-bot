"""v0.7 discovery/community endpoints: all writes require authentication.

Public reads never return private character definitions, private conversations,
email addresses, or the reporter identity from moderation reports.
"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_, cast, String, distinct
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.security import current_user
from app.models.entities import (User, Character, Conversation, UserProfile, Favorite,
    Collection, CollectionItem, CreatorFollow, CharacterRating, CommunityReport)
from app.api.community_schemas import (ProfileEdit, PublicProfile, CollectionIn, CollectionOut,
    RatingIn, ReportIn, SearchPage)

router = APIRouter(prefix="/api/v1", tags=["Community"])

async def available_character(db, character_id, viewer_id=None):
    item = await db.get(Character, character_id)
    if not item or ((not item.is_public or item.moderation_status != "active") and item.creator_id != viewer_id):
        raise HTTPException(404, "Character not found")
    return item

async def public_character(db, character_id):
    item = await db.get(Character, character_id)
    if not item or not item.is_public or item.moderation_status != "active":
        raise HTTPException(404, "Character not found")
    return item

async def mine_collection(db, collection_id, user_id):
    obj = await db.get(Collection, collection_id)
    if not obj or obj.user_id != user_id:
        raise HTTPException(404, "Collection not found")
    return obj

async def creator_profile(db, creator_id, viewer_id=None):
    creator = await db.get(User, creator_id)
    if not creator:
        raise HTTPException(404, "Creator not found")
    profile = await db.get(UserProfile, creator_id)
    followers = await db.scalar(select(func.count()).select_from(CreatorFollow).where(CreatorFollow.creator_id == creator_id))
    following = viewer_id is not None and await db.get(CreatorFollow, (viewer_id, creator_id)) is not None
    return PublicProfile(user_id=creator.id, handle=profile.handle if profile else "",
        display_name=creator.display_name, bio=profile.bio if profile else "",
        avatar_url=profile.avatar_url if profile else "", follower_count=followers or 0, is_following=following)

@router.get("/creators/{creator_id}", response_model=PublicProfile)
async def get_creator(creator_id: str, db: AsyncSession = Depends(get_db)):
    return await creator_profile(db, creator_id)

@router.put("/creators/me", response_model=PublicProfile)
async def update_my_profile(payload: ProfileEdit, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    profile = await db.get(UserProfile, user.id)
    if profile is None:
        profile = UserProfile(user_id=user.id, **payload.model_dump())
        db.add(profile)
    else:
        for k, v in payload.model_dump().items():
            setattr(profile, k, v)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Handle already in use")
    return await creator_profile(db, user.id, user.id)

@router.post("/creators/{creator_id}/follow", status_code=204)
async def follow_creator(creator_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    if creator_id == user.id:
        raise HTTPException(400, "Cannot follow yourself")
    if not await db.get(User, creator_id):
        raise HTTPException(404, "Creator not found")
    if not await db.get(CreatorFollow, (user.id, creator_id)):
        db.add(CreatorFollow(follower_id=user.id, creator_id=creator_id))
        await db.commit()

@router.delete("/creators/{creator_id}/follow", status_code=204)
async def unfollow_creator(creator_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    obj = await db.get(CreatorFollow, (user.id, creator_id))
    if obj:
        await db.delete(obj)
        await db.commit()

@router.get("/creators/{creator_id}/characters", response_model=SearchPage)
async def creator_characters(creator_id: str, limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0), db: AsyncSession = Depends(get_db)):
    if not await db.get(User, creator_id):
        raise HTTPException(404, "Creator not found")
    return await build_discovery(db, creator_id=creator_id, limit=limit, offset=offset, sort="newest")

@router.get("/characters/discover", response_model=SearchPage)
async def discover(q: str = Query("", max_length=120), tag: str = Query("", max_length=32),
                   category: str = Query("", max_length=32), sort: str = Query("trending", pattern="^(trending|popular|newest|rating)$"),
                   limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0), db: AsyncSession = Depends(get_db)):
    # Category is a tag-based filter in v0.7; tags are creator-controlled.
    if tag and category and tag.lower() != category.lower():
        raise HTTPException(422, "Use either tag or category")
    return await build_discovery(db, query=q, tag=tag or category, sort=sort, limit=limit, offset=offset)

async def build_discovery(db, *, query="", tag="", sort="trending", creator_id=None, limit=20, offset=0):
    fav_count = (select(Favorite.character_id.label("cid"), func.count().label("total"))
                 .group_by(Favorite.character_id).subquery())
    chat_count = (select(Conversation.character_id.label("cid"), func.count(distinct(Conversation.user_id)).label("total"))
                  .group_by(Conversation.character_id).subquery())
    rating_agg = (select(CharacterRating.character_id.label("cid"), func.avg(CharacterRating.stars).label("avg"),
                         func.count().label("total")).group_by(CharacterRating.character_id).subquery())
    recent_favs = (select(Favorite.character_id.label("cid"), func.count().label("total"))
                   .where(Favorite.created_at >= datetime.now(timezone.utc) - timedelta(days=7))
                   .group_by(Favorite.character_id).subquery())
    count_f = func.coalesce(fav_count.c.total, 0)
    count_c = func.coalesce(chat_count.c.total, 0)
    count_r = func.coalesce(rating_agg.c.total, 0)
    trend = func.coalesce(recent_favs.c.total, 0)
    q = select(Character, count_f, count_c, rating_agg.c.avg, count_r).outerjoin(fav_count, fav_count.c.cid == Character.id) \
        .outerjoin(chat_count, chat_count.c.cid == Character.id) \
        .outerjoin(rating_agg, rating_agg.c.cid == Character.id) \
        .outerjoin(recent_favs, recent_favs.c.cid == Character.id).where((Character.is_public.is_(True) & (Character.moderation_status == "active")))
    predicates = []
    if creator_id:
        predicates.append(Character.creator_id == creator_id)
    if query.strip():
        term = f"%{escape_like(query.strip().lower())}%"
        predicates.append(or_(func.lower(Character.name).like(term, escape="!"),
            func.lower(Character.tagline).like(term, escape="!"),
            func.lower(cast(Character.tags, String)).like(term, escape="!")))
    if tag.strip():
        tag_term = '%"' + escape_like(tag.strip().lower()) + '"%'
        predicates.append(func.lower(cast(Character.tags, String)).like(tag_term, escape="!"))
    for p in predicates:
        q = q.where(p)
    count_query = select(func.count()).select_from(Character).where((Character.is_public.is_(True) & (Character.moderation_status == "active")))
    for p in predicates:
        count_query = count_query.where(p)
    total = await db.scalar(count_query)
    orders = {
        "newest": [Character.created_at.desc()],
        "popular": [(count_f * 2 + count_c * 3 + count_r).desc(), Character.created_at.desc()],
        "rating": [rating_agg.c.avg.desc().nullslast(), count_r.desc(), Character.created_at.desc()],
        "trending": [(trend * 3 + count_c).desc(), Character.created_at.desc()],
    }
    rows = (await db.execute(q.order_by(*orders[sort], Character.id).offset(offset).limit(limit))).all()
    return {"items": [{"id": c.id, "creator_id": c.creator_id, "name": c.name,
        "tagline": c.tagline, "tags": c.tags or [], "favorites": int(f), "chats": int(ch),
        "average_rating": round(float(avg), 2) if avg is not None else None,
        "rating_count": int(rc)} for c, f, ch, avg, rc in rows],
        "total": total or 0, "offset": offset, "limit": limit}

def escape_like(value):
    return value.replace("!", "!!").replace("%", "!%").replace("_", "!_")

@router.get("/favorites")
async def list_favorites(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(Character).join(Favorite, Favorite.character_id == Character.id)
        .where(Favorite.user_id == user.id, ((Character.is_public.is_(True) & (Character.moderation_status == "active"))) | (Character.creator_id == user.id))
        .order_by(Favorite.created_at.desc()))
    return [{"id": c.id, "name": c.name, "tagline": c.tagline, "creator_id": c.creator_id} for c in rows.all()]

@router.post("/favorites/{character_id}", status_code=204)
async def favorite(character_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await available_character(db, character_id, user.id)
    if not await db.get(Favorite, (user.id, character_id)):
        db.add(Favorite(user_id=user.id, character_id=character_id))
        await db.commit()

@router.delete("/favorites/{character_id}", status_code=204)
async def unfavorite(character_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    item = await db.get(Favorite, (user.id, character_id))
    if item:
        await db.delete(item)
        await db.commit()

@router.get("/collections", response_model=list[CollectionOut])
async def collections(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(Collection).where(Collection.user_id == user.id)
        .order_by(Collection.created_at.desc()))).all()

@router.post("/collections", response_model=CollectionOut, status_code=201)
async def create_collection(payload: CollectionIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    count = await db.scalar(select(func.count()).select_from(Collection).where(Collection.user_id == user.id))
    if count >= 50:
        raise HTTPException(409, "Collection limit reached")
    record = Collection(user_id=user.id, **payload.model_dump())
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record

@router.patch("/collections/{collection_id}", response_model=CollectionOut)
async def edit_collection(collection_id: str, payload: CollectionIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    item = await mine_collection(db, collection_id, user.id)
    for k, v in payload.model_dump().items():
        setattr(item, k, v)
    await db.commit()
    return item

@router.delete("/collections/{collection_id}", status_code=204)
async def delete_collection(collection_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    item = await mine_collection(db, collection_id, user.id)
    await db.delete(item)
    await db.commit()

@router.get("/collections/{collection_id}/characters")
async def collection_characters(collection_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await mine_collection(db, collection_id, user.id)
    chars = await db.scalars(select(Character).join(CollectionItem, CollectionItem.character_id == Character.id)
        .where(CollectionItem.collection_id == collection_id,
            ((Character.is_public.is_(True) & (Character.moderation_status == "active"))) | (Character.creator_id == user.id))
        .order_by(CollectionItem.added_at.desc()))
    return [{"id": c.id, "name": c.name, "tagline": c.tagline, "creator_id": c.creator_id} for c in chars.all()]

@router.post("/collections/{collection_id}/characters/{character_id}", status_code=204)
async def add_collection_character(collection_id: str, character_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await mine_collection(db, collection_id, user.id)
    await available_character(db, character_id, user.id)
    if not await db.get(CollectionItem, (collection_id, character_id)):
        count = await db.scalar(select(func.count()).select_from(CollectionItem).where(CollectionItem.collection_id == collection_id))
        if count >= 200:
            raise HTTPException(409, "Collection is full")
        db.add(CollectionItem(collection_id=collection_id, character_id=character_id))
        await db.commit()

@router.delete("/collections/{collection_id}/characters/{character_id}", status_code=204)
async def remove_collection_character(collection_id: str, character_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await mine_collection(db, collection_id, user.id)
    obj = await db.get(CollectionItem, (collection_id, character_id))
    if obj:
        await db.delete(obj)
        await db.commit()

@router.get("/characters/{character_id}/community")
async def character_community(character_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    c = await available_character(db, character_id, user.id)
    count = await db.scalar(select(func.count()).select_from(Favorite).where(Favorite.character_id == character_id))
    rating = await db.execute(select(func.avg(CharacterRating.stars), func.count())
        .where(CharacterRating.character_id == character_id))
    avg, rated = rating.one()
    my_rating = await db.get(CharacterRating, (user.id, character_id))
    return {"favorite": await db.get(Favorite, (user.id, character_id)) is not None,
        "favorites": count or 0, "average_rating": round(float(avg), 2) if avg else None,
        "rating_count": rated, "my_rating": my_rating.stars if my_rating else None,
        "share_path": f"/?character={c.id}" if c.is_public else None}

@router.put("/characters/{character_id}/rating", status_code=204)
async def rate_character(character_id: str, payload: RatingIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    c = await public_character(db, character_id)
    if c.creator_id == user.id:
        raise HTTPException(403, "Cannot rate your own character")
    item = await db.get(CharacterRating, (user.id, character_id))
    if item:
        item.stars = payload.stars
    else:
        db.add(CharacterRating(user_id=user.id, character_id=character_id, stars=payload.stars))
    await db.commit()

@router.delete("/characters/{character_id}/rating", status_code=204)
async def clear_rating(character_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    item = await db.get(CharacterRating, (user.id, character_id))
    if item:
        await db.delete(item)
        await db.commit()

@router.post("/characters/{character_id}/reports", status_code=201)
async def report_character(character_id: str, payload: ReportIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await public_character(db, character_id)
    if await db.scalar(select(CommunityReport.id).where(
        CommunityReport.reporter_id == user.id, CommunityReport.character_id == character_id)):
        raise HTTPException(409, "Already reported")
    db.add(CommunityReport(reporter_id=user.id, character_id=character_id, **payload.model_dump()))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Already reported")
    return {"status": "received"}
