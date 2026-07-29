from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.intelligence import IntelligenceReportRead
from app.schemas.youtube_analytics import (
    ScatterPoint,
    SummaryRead,
    TimeseriesPoint,
    TopVideoRead,
    UploadBucket,
    VideoRowRead,
)
from app.services import youtube_analytics as analytics
from app.services import youtube_intelligence_adapter

router = APIRouter(prefix="/api/integrations/youtube/analytics", tags=["YouTube Analytics"])


@router.get("/summary", response_model=SummaryRead)
def summary(db: Session = Depends(get_db)):
    return analytics.get_summary(db)


@router.get("/timeseries", response_model=list[TimeseriesPoint])
def timeseries(metric: str = Query(default="views", pattern="^(views|likes|comments)$"), db: Session = Depends(get_db)):
    return analytics.get_timeseries(db, metric)


@router.get("/upload-frequency", response_model=list[UploadBucket])
def upload_frequency(interval: str = Query(default="month", pattern="^(week|month)$"), db: Session = Depends(get_db)):
    return analytics.get_upload_frequency(db, interval)


@router.get("/top", response_model=list[TopVideoRead])
def top(
    metric: str = Query(default="views", pattern="^(views|engagement)$"),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    return analytics.get_top_videos(db, metric, limit)


@router.get("/recent", response_model=list[VideoRowRead])
def recent(limit: int = Query(default=10, ge=1, le=50), db: Session = Depends(get_db)):
    return analytics.get_recent_video_rows(db, limit)


@router.get("/scatter", response_model=list[ScatterPoint])
def scatter(db: Session = Depends(get_db)):
    return analytics.get_scatter(db)


@router.get("/intelligence", response_model=IntelligenceReportRead)
def intelligence(db: Session = Depends(get_db)):
    return youtube_intelligence_adapter.get_intelligence_report(db)
