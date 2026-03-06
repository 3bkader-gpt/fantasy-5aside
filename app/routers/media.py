import os
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import models
from ..dependencies import get_current_admin_league, get_match_repository, IMatchRepository


UPLOAD_DIR = "uploads"

router = APIRouter(tags=["media"])


def _ensure_upload_dir() -> None:
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/l/{slug}/match/{match_id}/media")
async def upload_match_media(
    slug: str,
    match_id: int,
    files: List[UploadFile] = File(...),
    league: models.League = Depends(get_current_admin_league),
    match_repo: IMatchRepository = Depends(get_match_repository),
    db: Session = Depends(get_db),
):
    """Admin-only: upload 1–N images for a match."""
    _ensure_upload_dir()

    match = match_repo.get_by_id(match_id)
    if not match or match.league_id != league.id:
        raise HTTPException(status_code=404, detail="Match not found")

    if len(files) > 5:
        raise HTTPException(status_code=400, detail="يمكن رفع 5 ملفات كحد أقصى في الطلب الواحد.")

    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    max_size = 5 * 1024 * 1024  # 5MB

    created_items: list[models.MatchMedia] = []

    ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }

    for f in files:
        if f.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"نوع الملف غير مدعوم: {f.content_type}")
        raw = await f.read()
        if len(raw) > max_size:
            raise HTTPException(status_code=400, detail="حجم كل ملف يجب ألا يتجاوز 5MB.")

        ext = ext_map.get(f.content_type, ".bin")
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
    return {"success": True, "count": len(created_items)}


@router.delete("/l/{slug}/media/{media_id}")
async def delete_match_media(
    slug: str,
    media_id: int,
    league: models.League = Depends(get_current_admin_league),
    db: Session = Depends(get_db),
):
    """Admin-only: delete a media item and its file."""
    media = db.query(models.MatchMedia).filter_by(id=media_id, league_id=league.id).first()
    if not media:
        raise HTTPException(status_code=404, detail="الصورة غير موجودة.")

    path = os.path.join(UPLOAD_DIR, media.filename)
    db.delete(media)
    db.commit()

    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            # Ignore file system errors; DB row is already gone
            pass

    return {"success": True}
