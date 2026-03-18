import os
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

import logging
from ..core.config import settings
from ..database import get_db
from ..models import models
from ..dependencies import get_current_admin_league, get_match_repository, IMatchRepository

logger = logging.getLogger(__name__)

UPLOAD_DIR = "uploads"
BUCKET_MATCH_MEDIA = "match-media"

router = APIRouter(tags=["media"])


def _ensure_upload_dir() -> None:
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR, exist_ok=True)


def _supabase_storage_upload(league_id: int, match_id: int, raw: bytes, ext: str, content_type: str) -> tuple[str, str] | None:
    """Upload to Supabase Storage. Returns (storage_path, public_url) or None if not configured."""
    if not settings.supabase_project_url or not settings.supabase_service_role_key:
        return None
    try:
        from supabase import create_client
        client = create_client(settings.supabase_project_url, settings.supabase_service_role_key)
        path = f"{league_id}/{match_id}/{uuid.uuid4().hex}{ext}"
        client.storage.from_(BUCKET_MATCH_MEDIA).upload(path, raw, {"content-type": content_type})
        public_url = client.storage.from_(BUCKET_MATCH_MEDIA).get_public_url(path)
        return (path, public_url)
    except Exception as e:
        logger.error(f"Supabase upload failed: {str(e)}")
        return None


def _supabase_storage_remove(storage_path: str) -> bool:
    """Remove file from Supabase Storage. Returns True if removed or not configured."""
    if not settings.supabase_project_url or not settings.supabase_service_role_key:
        return True
    try:
        from supabase import create_client
        client = create_client(settings.supabase_project_url, settings.supabase_service_role_key)
        client.storage.from_(BUCKET_MATCH_MEDIA).remove([storage_path])
        return True
    except Exception as e:
        logger.error(f"Supabase removal failed for {storage_path}: {str(e)}")
        return False


@router.post("/l/{slug}/match/{match_id}/media")
async def upload_match_media(
    slug: str,
    match_id: int,
    files: List[UploadFile] = File(...),
    league: models.League = Depends(get_current_admin_league),
    match_repo: IMatchRepository = Depends(get_match_repository),
    db: Session = Depends(get_db),
):
    """Admin-only: upload 1–N images for a match. Uses Supabase Storage if configured, else local uploads/."""
    match = match_repo.get_by_id_for_league(league.id, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    if len(files) > 5:
        raise HTTPException(status_code=400, detail="يمكن رفع 5 ملفات كحد أقصى في الطلب الواحد.")

    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    max_size = 5 * 1024 * 1024  # 5MB

    ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }

    use_supabase = bool(settings.supabase_project_url and settings.supabase_service_role_key)
    if not use_supabase:
        _ensure_upload_dir()

    created_items: list[models.MatchMedia] = []

    for f in files:
        if f.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"نوع الملف غير مدعوم: {f.content_type}")
        raw = await f.read()
        if len(raw) > max_size:
            raise HTTPException(status_code=400, detail="حجم كل ملف يجب ألا يتجاوز 5MB.")

        ext = ext_map.get(f.content_type, ".bin")

        if use_supabase:
            result = _supabase_storage_upload(league.id, match.id, raw, ext, f.content_type)
            if result:
                storage_path, public_url = result
                media = models.MatchMedia(
                    league_id=league.id,
                    match_id=match.id,
                    filename=storage_path,
                    original_name=f.filename,
                    mime_type=f.content_type,
                    size_bytes=len(raw),
                    file_url=public_url,
                )
                logger.info(f"Uploaded to Supabase: {public_url}")
            else:
                # Fallback to local if Supabase upload failed
                logger.warning(f"Supabase upload failed for {f.filename}, falling back to local storage")
                filename = f"{uuid.uuid4().hex}{ext}"
                path = os.path.join(UPLOAD_DIR, filename)
                with open(path, "wb") as out:
                    out.write(raw)
                media = models.MatchMedia(
                    league_id=league.id,
                    match_id=match.id,
                    filename=filename,
                    original_name=f.filename,
                    mime_type=f.content_type,
                    size_bytes=len(raw),
                )
        else:
            filename = f"{uuid.uuid4().hex}{ext}"
            path = os.path.join(UPLOAD_DIR, filename)
            with open(path, "wb") as out:
                out.write(raw)
            media = models.MatchMedia(
                league_id=league.id,
                match_id=match.id,
                filename=filename,
                original_name=f.filename,
                mime_type=f.content_type,
                size_bytes=len(raw),
            )
        db.add(media)
        created_items.append(media)

    db.commit()
    logger.info(f"Successfully uploaded {len(created_items)} media items for match {match_id}")
    return {"success": True, "count": len(created_items)}


@router.delete("/l/{slug}/media/{media_id}")
async def delete_match_media(
    slug: str,
    media_id: int,
    league: models.League = Depends(get_current_admin_league),
    db: Session = Depends(get_db),
):
    """Admin-only: delete a media item and its file (from Supabase Storage or local uploads)."""
    media = db.query(models.MatchMedia).filter_by(id=media_id, league_id=league.id).first()
    if not media:
        raise HTTPException(status_code=404, detail="الصورة غير موجودة.")

    if media.file_url:
        _supabase_storage_remove(media.filename)
    else:
        path = os.path.join(UPLOAD_DIR, media.filename)
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    db.delete(media)
    db.commit()
    logger.info(f"Deleted media {media_id} for league {league.id}")
    return {"success": True}
