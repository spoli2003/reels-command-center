from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.reel import Reel
from app.schemas.reel import ReelCreate, ReelRead

router = APIRouter(prefix="/api/reels", tags=["reels"])


@router.get("", response_model=list[ReelRead])
def list_reels(db: Session = Depends(get_db)):
    return db.scalars(select(Reel).order_by(Reel.created_at.desc())).all()


@router.post("", response_model=ReelRead, status_code=status.HTTP_201_CREATED)
def create_reel(payload: ReelCreate, db: Session = Depends(get_db)):
    reel = Reel(title=payload.title, category=payload.category, hook=payload.hook)
    db.add(reel)
    db.commit()
    db.refresh(reel)
    return reel


@router.get("/{reel_id}", response_model=ReelRead)
def get_reel(reel_id: int, db: Session = Depends(get_db)):
    reel = db.get(Reel, reel_id)
    if reel is None:
        raise HTTPException(status_code=404, detail="Reel not found")
    return reel
