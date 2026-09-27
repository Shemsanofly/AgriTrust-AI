"""Crop photos taken by the farmer.

Files are checked by their content (JPEG, PNG or WebP signature, not the name the phone
sends), capped in size and count, stored under a random name in UPLOAD_DIR/crops and
served only to the farm's owner (and admins, audited). The web app shrinks photos before
upload, so a slow connection only sends a few hundred KB."""

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from .. import files
from ..db import get_session
from ..models import Crop, CropPhoto, User
from ..security.audit import audit
from ..security.auth import get_current_user
from .farms import load_farm

router = APIRouter(tags=["shambani"])
MAX_PER_CROP = 12


def photo_dir() -> Path:
    return files.upload_dir("crops")


def photo_json(p: CropPhoto) -> dict:
    return {"id": p.id, "crop_id": p.crop_id, "url": f"/crop-photos/{p.id}", "caption": p.caption, "created_at": p.created_at.isoformat()}


def photos_for(session: Session, crop_id: int) -> list[dict]:
    rows = session.exec(select(CropPhoto).where(CropPhoto.crop_id == crop_id).order_by(CropPhoto.created_at.desc()))  # type: ignore[attr-defined]
    return [photo_json(p) for p in rows]


def load_crop(session: Session, crop_id: int, user: User) -> Crop:
    crop = session.get(Crop, crop_id)
    if not crop:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    load_farm(session, crop.farm_id, user)  # owner farmer or admin only
    return crop


@router.post("/crops/{crop_id}/photos", status_code=201)
async def upload_photo(
    crop_id: int,
    file: UploadFile = File(...),
    caption: str = Form(default="", max_length=140),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    crop = load_crop(session, crop_id, user)
    count = len(session.exec(select(CropPhoto.id).where(CropPhoto.crop_id == crop.id)).all())
    if count >= MAX_PER_CROP:
        raise HTTPException(status.HTTP_409_CONFLICT, "too_many_photos")
    data = await file.read(files.MAX_BYTES + 1)
    if len(data) > files.MAX_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "photo_too_large")
    kind = files.sniff(data[:16])
    if kind not in files.IMAGES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "not_an_image")
    name = files.save("crops", data, kind)
    photo = CropPhoto(crop_id=crop.id, farm_id=crop.farm_id, stored_name=name, content_type=kind, size_bytes=len(data), caption=caption.strip())
    session.add(photo)
    audit(session, user.id, "CROP_PHOTO_ADDED", "CROP", crop.id)
    session.commit()
    session.refresh(photo)
    return photo_json(photo)


@router.get("/crops/{crop_id}/photos")
def list_photos(crop_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    crop = load_crop(session, crop_id, user)
    return photos_for(session, crop.id)


@router.get("/crop-photos/{photo_id}")
def get_photo(photo_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    photo = session.get(CropPhoto, photo_id)
    if not photo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    load_crop(session, photo.crop_id, user)
    path = photo_dir() / photo.stored_name
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return FileResponse(path, media_type=photo.content_type, headers={"Cache-Control": "private, max-age=86400"})


@router.delete("/crop-photos/{photo_id}", status_code=204)
def delete_photo(photo_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    photo = session.get(CropPhoto, photo_id)
    if not photo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    crop = load_crop(session, photo.crop_id, user)
    (photo_dir() / photo.stored_name).unlink(missing_ok=True)
    session.delete(photo)
    audit(session, user.id, "CROP_PHOTO_DELETED", "CROP", crop.id)
    session.commit()
