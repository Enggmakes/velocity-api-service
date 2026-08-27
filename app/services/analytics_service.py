import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.models import ActivityEvent, Heartbeat, GitHubEvent
from app.config import settings


class AnalyticsService:
    """Computes dwell times, active sessions, commits, and aggregate metrics per tenant/user."""

    @staticmethod
    def calculate_active_time(heartbeats: List[Heartbeat], timeout_seconds: int = 300) -> int:
        """
        Calculate total active coding duration in seconds from heartbeats.
        Heartbeats within `timeout_seconds` of each other count as continuous coding.
        """
        if not heartbeats:
            return 0

        # Sort heartbeats chronologically
        sorted_beats = sorted(heartbeats, key=lambda x: x.timestamp)
        total_seconds = 0
        last_beat_time = sorted_beats[0].timestamp

        # Standard minimal heartbeat credit is 60 seconds
        total_seconds += 60

        for beat in sorted_beats[1:]:
            delta = (beat.timestamp - last_beat_time).total_seconds()
            if delta <= timeout_seconds:
                total_seconds += int(delta)
            else:
                total_seconds += 60
            last_beat_time = beat.timestamp

        return total_seconds

    @staticmethod
    def format_duration(seconds: int) -> str:
        """Convert seconds into human-readable format (e.g. '2h 15m' or '45m')."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    @staticmethod
    @staticmethod
    def get_today_stats(db: Session, api_key_id: Optional[int] = None, is_admin: bool = False) -> Dict[str, Any]:
        """Compute all stats for the current UTC day isolated by user api_key_id or all for admin."""
        today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        # 1. Base queries with tenant isolation
        hb_query = db.query(Heartbeat).filter(Heartbeat.timestamp >= today_start)
        ev_query = db.query(ActivityEvent).filter(ActivityEvent.timestamp >= today_start)

        if not is_admin:
            if api_key_id is not None:
                hb_query = hb_query.filter(Heartbeat.api_key_id == api_key_id)
                ev_query = ev_query.filter(ActivityEvent.api_key_id == api_key_id)
            else:
                hb_query = hb_query.filter(Heartbeat.api_key_id.is_(None))
                ev_query = ev_query.filter(ActivityEvent.api_key_id.is_(None))

        heartbeats = hb_query.all()
        active_seconds = AnalyticsService.calculate_active_time(heartbeats, settings.HEARTBEAT_TIMEOUT_SECONDS)
        total_events = ev_query.count()

        commits_today = ev_query.filter(ActivityEvent.event_type.in_(["commit", "PushEvent"])).count()

        # 3. Active projects today
        projects_query = hb_query.with_entities(Heartbeat.project_name).distinct().all()
        active_projects = [p[0] for p in projects_query if p[0]]

        # 4. Top languages today
        langs_query = hb_query.with_entities(Heartbeat.language, func.count(Heartbeat.id))\
            .filter(Heartbeat.language.isnot(None))\
            .group_by(Heartbeat.language)\
            .order_by(desc(func.count(Heartbeat.id)))\
            .all()
        top_languages = {lang: count for lang, count in langs_query if lang and lang != "other"}

        # 5. Current status check (active in last 5 minutes?)
        latest_hb_query = db.query(Heartbeat)
        if not is_admin:
            if api_key_id is not None:
                latest_hb_query = latest_hb_query.filter(Heartbeat.api_key_id == api_key_id)
            else:
                latest_hb_query = latest_hb_query.filter(Heartbeat.api_key_id.is_(None))

        latest_hb = latest_hb_query.order_by(desc(Heartbeat.timestamp)).first()
        is_coding = False
        last_activity_ago = None
        if latest_hb:
            diff_secs = (datetime.datetime.utcnow() - latest_hb.timestamp).total_seconds()
            last_activity_ago = max(0, int(diff_secs // 60))
            is_coding = diff_secs <= settings.HEARTBEAT_TIMEOUT_SECONDS

        return {
            "date": today_start.strftime("%Y-%m-%d"),
            "active_coding_seconds": active_seconds,
            "active_coding_formatted": AnalyticsService.format_duration(active_seconds),
            "total_events": total_events,
            "commits_today": commits_today,
            "active_projects": active_projects,
            "top_languages": top_languages,
            "is_currently_coding": is_coding,
            "last_activity_ago_minutes": last_activity_ago
        }

    @staticmethod
    def get_weekly_stats(db: Session, api_key_id: Optional[int] = None, is_admin: bool = False) -> Dict[str, Any]:
        """Compute daily active coding time and events for the last 7 days per user or for admin."""
        now = datetime.datetime.utcnow()
        days_data = []

        for i in range(6, -1, -1):
            day_date = (now - datetime.timedelta(days=i)).date()
            start_dt = datetime.datetime.combine(day_date, datetime.time.min)
            end_dt = datetime.datetime.combine(day_date, datetime.time.max)

            hb_q = db.query(Heartbeat).filter(Heartbeat.timestamp.between(start_dt, end_dt))
            ev_q = db.query(ActivityEvent).filter(ActivityEvent.timestamp.between(start_dt, end_dt))

            if not is_admin:
                if api_key_id is not None:
                    hb_q = hb_q.filter(Heartbeat.api_key_id == api_key_id)
                    ev_q = ev_q.filter(ActivityEvent.api_key_id == api_key_id)
                else:
                    hb_q = hb_q.filter(Heartbeat.api_key_id.is_(None))
                    ev_q = ev_q.filter(ActivityEvent.api_key_id.is_(None))

            heartbeats = hb_q.all()
            active_secs = AnalyticsService.calculate_active_time(heartbeats, settings.HEARTBEAT_TIMEOUT_SECONDS)
            event_count = ev_q.count()
            commits = ev_q.filter(ActivityEvent.event_type.in_(["commit", "PushEvent"])).count()

            days_data.append({
                "date": day_date.strftime("%Y-%m-%d"),
                "day_name": day_date.strftime("%a"),
                "active_seconds": active_secs,
                "active_hours": round(active_secs / 3600, 2),
                "active_formatted": AnalyticsService.format_duration(active_secs),
                "events": event_count,
                "commits": commits
            })

        return {"weekly_breakdown": days_data}

    @staticmethod
    def get_projects_summary(db: Session, api_key_id: Optional[int] = None, is_admin: bool = False) -> List[Dict[str, Any]]:
        """Compute metrics aggregated per project for the given user or admin."""
        hb_q = db.query(Heartbeat)
        if not is_admin:
            if api_key_id is not None:
                hb_q = hb_q.filter(Heartbeat.api_key_id == api_key_id)
            else:
                hb_q = hb_q.filter(Heartbeat.api_key_id.is_(None))

        projects = hb_q.with_entities(Heartbeat.project_name).distinct().all()
        project_list = [p[0] for p in projects if p[0]]

        results = []
        for proj in project_list:
            proj_hb_q = hb_q.filter(Heartbeat.project_name == proj)
            proj_ev_q = db.query(ActivityEvent).filter(ActivityEvent.project_name == proj)
            if not is_admin:
                if api_key_id is not None:
                    proj_ev_q = proj_ev_q.filter(ActivityEvent.api_key_id == api_key_id)
                else:
                    proj_ev_q = proj_ev_q.filter(ActivityEvent.api_key_id.is_(None))

            heartbeats = proj_hb_q.all()
            active_secs = AnalyticsService.calculate_active_time(heartbeats, settings.HEARTBEAT_TIMEOUT_SECONDS)
            total_events = proj_ev_q.count()
            total_commits = proj_ev_q.filter(ActivityEvent.event_type.in_(["commit", "PushEvent"])).count()

            last_hb = proj_hb_q.order_by(desc(Heartbeat.timestamp)).first()
            last_active = last_hb.timestamp if last_hb else None

            top_langs = proj_hb_q.with_entities(Heartbeat.language, func.count(Heartbeat.id))\
                .filter(Heartbeat.language.isnot(None))\
                .group_by(Heartbeat.language)\
                .order_by(desc(func.count(Heartbeat.id)))\
                .limit(3)\
                .all()

            results.append({
                "project_name": proj,
                "total_active_seconds": active_secs,
                "total_active_formatted": AnalyticsService.format_duration(active_secs),
                "total_events": total_events,
                "total_commits": total_commits,
                "last_active": last_active,
                "top_languages": [l[0] for l in top_langs if l[0] and l[0] != "other"]
            })

        results.sort(key=lambda x: x["total_active_seconds"], reverse=True)
        return results
