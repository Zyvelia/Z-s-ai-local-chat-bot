"""v1.3 image security, ownership, schema, and upload constraints."""
from io import BytesIO
from types import SimpleNamespace
import pytest
from PIL import Image
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
from app.api.media import normalize_image, assert_scope, can_read, MAX_UPLOAD_BYTES
from app.api.schemas import CharacterIn, CharacterEdit
from app.models.entities import MediaAsset, Character, Conversation, Persona


def sample_image(format="JPEG", color=(45, 50, 55)):
    out = BytesIO()
    Image.new('RGB', (12, 10), color).save(out, format=format)
    return out.getvalue()


def test_reencodes_jpeg_to_png_and_strips_exif():
    normalized = normalize_image(sample_image())
    with Image.open(BytesIO(normalized)) as img:
        assert img.format == "PNG"
        assert img.size == (12, 10)
        assert not img.getexif()


def test_webp_and_png_supported():
    for ext in ['PNG', 'WEBP']:
        assert normalize_image(sample_image(ext)).startswith(b'\x89PNG')


@pytest.mark.parametrize('payload', [b'', b'<svg><script/></svg>', b'not an image', b'0' * (MAX_UPLOAD_BYTES+1)])
def test_bad_uploads_rejected(payload):
    with pytest.raises(ValueError):
        normalize_image(payload)


def test_oversize_pixel_dimensions_rejected():
    out = BytesIO()
    Image.new('RGB', (4000, 3200)).save(out, format='PNG')
    with pytest.raises(ValueError):
        normalize_image(out.getvalue())


def test_character_appearance_validation():
    ok = CharacterIn(name='A', personality='B', appearance_description='silver eyes', appearance_style='anime', accent_color='#AABBCC')
    assert ok.appearance_style == 'anime'
    for changes in [{'accent_color':'red'}, {'appearance_style':'unknown'}]:
        with pytest.raises(Exception):
            CharacterEdit(**changes)


def test_media_table_postgres_schema():
    ddl = str(CreateTable(MediaAsset.__table__).compile(dialect=postgresql.dialect()))
    assert 'media_assets' in ddl and 'owner_id' in ddl and 'purpose' in ddl


class FakeDb:
    def __init__(self, mapping): self.mapping = mapping
    async def get(self, model, id): return self.mapping.get((model, id))


@pytest.mark.asyncio
async def test_media_scope_rejects_non_owner():
    db = FakeDb({(Character, 'c'): SimpleNamespace(creator_id='other')})
    with pytest.raises(HTTPException) as raised:
        await assert_scope(SimpleNamespace(id='me'), db, 'avatar', 'c', None, None)
    assert raised.value.status_code == 404


@pytest.mark.asyncio
async def test_media_scope_rejects_multiple_targets():
    with pytest.raises(HTTPException) as raised:
        await assert_scope(SimpleNamespace(id='me'), FakeDb({}), 'avatar', 'c', 'chat', None)
    assert raised.value.status_code == 422


@pytest.mark.asyncio
async def test_character_asset_visibility_and_private_chat():
    me = SimpleNamespace(id='me')
    stranger = SimpleNamespace(id='stranger')
    avatar = SimpleNamespace(owner_id='me', character_id='c', conversation_id=None)
    background = SimpleNamespace(owner_id='me', character_id=None, conversation_id='chat')
    db = FakeDb({(Character, 'c'): SimpleNamespace(is_public=True, moderation_status='active')})
    assert await can_read(avatar, me, db)
    assert await can_read(avatar, stranger, db)
    assert not await can_read(background, stranger, db)
    db.mapping[(Character, 'c')].moderation_status = 'hidden'
    assert not await can_read(avatar, stranger, db)
