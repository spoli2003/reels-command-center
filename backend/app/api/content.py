from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.content import ContentVideo, MetricSnapshot, Publication
from app.schemas.content import (
    ContentVideoCreate,
    ContentVideoRead,
    MetricSnapshotCreate,
    MetricSnapshotRead,
    PublicationCreate,
    PublicationRead,
)

router = APIRouter(prefix="/api/content", tags=["content"])


def _publication_read(publication: Publication) -> PublicationRead:
    latest = max(publication.snapshots, key=lambda item: item.captured_at) if publication.snapshots else None
    return PublicationRead(
        id=publication.id,
        platform=publication.platform,
        external_id=publication.external_id,
        url=publication.url,
        published_at=publication.published_at,
        latest_metrics=MetricSnapshotRead.model_validate(latest) if latest else None,
    )


def _video_read(video: ContentVideo) -> ContentVideoRead:
    publications = [_publication_read(item) for item in video.publications]
    latest = [item.latest_metrics for item in publications if item.latest_metrics]
    return ContentVideoRead(
        id=video.id,
        public_id=video.public_id,
        title=video.title,
        description=video.description,
        category=video.category,
        duration_seconds=video.duration_seconds,
        language=video.language,
        created_at=video.created_at,
        updated_at=video.updated_at,
        publications=publications,
        total_views=sum(item.views for item in latest),
        total_interactions=sum(item.likes + item.comments + item.shares + item.saves for item in latest),
    )


@router.post("/videos", response_model=ContentVideoRead, status_code=status.HTTP_201_CREATED)
def create_video(payload: ContentVideoCreate, db: Session = Depends(get_db)):
    video = ContentVideo(**payload.model_dump())
    db.add(video)
    db.commit()
    db.refresh(video)
    return _video_read(video)


@router.get("/videos", response_model=list[ContentVideoRead])
def list_videos(db: Session = Depends(get_db)):
    statement = select(ContentVideo).options(selectinload(ContentVideo.publications).selectinload(Publication.snapshots)).order_by(ContentVideo.created_at.desc())
    return [_video_read(item) for item in db.scalars(statement).all()]


@router.post("/videos/{video_id}/publications", response_model=PublicationRead, status_code=status.HTTP_201_CREATED)
def create_publication(video_id: int, payload: PublicationCreate, db: Session = Depends(get_db)):
    if db.get(ContentVideo, video_id) is None:
        raise HTTPException(status_code=404, detail="Content video not found")
    publication = Publication(content_video_id=video_id, **payload.model_dump())
    db.add(publication)
    db.commit()
    db.refresh(publication)
    return _publication_read(publication)


@router.post("/publications/{publication_id}/snapshots", response_model=MetricSnapshotRead, status_code=status.HTTP_201_CREATED)
def create_snapshot(publication_id: int, payload: MetricSnapshotCreate, db: Session = Depends(get_db)):
    if db.get(Publication, publication_id) is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    snapshot = MetricSnapshot(publication_id=publication_id, **payload.model_dump())
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot
