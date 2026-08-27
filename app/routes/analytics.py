import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import ActivityEvent, Heartbeat
from app.schemas import TodayStatsResponse, ProjectMetricsResponse, PublicStatusResponse, ActivityResponse
from app.services.analytics_service import AnalyticsService
from app.services.auth_service import verify_api_key

router = APIRouter(prefix="/api/v1", tags=["Analytics & Activity"])


@router.get("/stats/today", response_model=TodayStatsResponse, summary="Get today's coding time, commits, and languages")
def get_today_stats(
    db: Session = Depends(get_db),
    auth: dict = Depends(verify_api_key)
):
    """Returns today's active coding metrics isolated to the authenticated user/app."""
    stats = AnalyticsService.get_today_stats(db, api_key_id=auth.get("key_id"))
    stats["tenant_name"] = auth.get("name", "Personal Workspace")
    return stats


@router.get("/stats/weekly", summary="Get 7-day activity timeline breakdown")
def get_weekly_stats(
    db: Session = Depends(get_db),
    auth: dict = Depends(verify_api_key)
):
    """Returns the daily breakdown of coding hours for the past 7 days isolated to the user."""
    return AnalyticsService.get_weekly_stats(db, api_key_id=auth.get("key_id"))


@router.get("/projects", response_model=List[ProjectMetricsResponse], summary="List metrics by project")
def get_projects(
    db: Session = Depends(get_db),
    auth: dict = Depends(verify_api_key)
):
    """Returns tracked projects with total dwell times for the authenticated user."""
    return AnalyticsService.get_projects_summary(db, api_key_id=auth.get("key_id"))


@router.get("/activity/recent", response_model=List[ActivityResponse], summary="Get recent activity stream (sanitized)")
def get_recent_activity(
    limit: int = Query(30, ge=1, le=100),
    project: Optional[str] = None,
    db: Session = Depends(get_db),
    auth: dict = Depends(verify_api_key)
):
    """Returns recent activity events for the authenticated user."""
    api_key_id = auth.get("key_id")
    query = db.query(ActivityEvent)

    if api_key_id is not None:
        query = query.filter(ActivityEvent.api_key_id == api_key_id)
    else:
        query = query.filter(ActivityEvent.api_key_id.is_(None))

    if project:
        query = query.filter(ActivityEvent.project_name == project)

    events = query.order_by(desc(ActivityEvent.timestamp)).limit(limit).all()
    return events


@router.get("/public/status", response_model=PublicStatusResponse, summary="Zero-leak public status for portfolios")
def get_public_status(db: Session = Depends(get_db)):
    """
    PUBLIC endpoint - NO auth required.
    Strictly guaranteed zero-leak: does NOT return repository names, project paths, or commit messages.
    Returns only high-level status (coding / idle), hours today, and top languages.
    """
    today_stats = AnalyticsService.get_today_stats(db, api_key_id=None)

    top_langs = list(today_stats["top_languages"].keys())[:3]
    category = "Software Engineering"
    if any(l in ["typescript", "javascript", "react", "react-ts", "html", "css"] for l in top_langs):
        category = "Web Application Development"
    elif any(l in ["python", "rust", "go", "sql"] for l in top_langs):
        category = "Backend & Systems Development"

    status_str = "Coding" if today_stats["is_currently_coding"] else "Idle"

    return {
        "status": status_str,
        "current_activity_category": category,
        "active_hours_today": round(today_stats["active_coding_seconds"] / 3600, 2),
        "commits_today": today_stats["commits_today"],
        "top_languages": top_langs,
        "last_updated": datetime.datetime.utcnow()
    }


@router.get("/analytics/standup", summary="Generate AI Standup summary of today's work")
def get_daily_standup(
    db: Session = Depends(get_db),
    auth: dict = Depends(verify_api_key)
):
    """Generates an intelligent daily engineering standup report for Slack, Discord, or Notion."""
    from app.services.standup_service import StandupGeneratorService
    return StandupGeneratorService.generate_standup(db, api_key_id=auth.get("key_id"))
