import datetime as dt
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import ActivityEvent
from app.services.analytics_service import AnalyticsService


class StandupGeneratorService:
    """Generates human-readable, AI-structured daily engineering standups."""

    @staticmethod
    def generate_standup(db: Session, api_key_id: Optional[int] = None) -> Dict[str, Any]:
        today = dt.date.today()
        today_stats = AnalyticsService.get_today_stats(db, api_key_id=api_key_id)

        # Query recent events today for this user
        today_start = dt.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        ev_query = db.query(ActivityEvent).filter(ActivityEvent.timestamp >= today_start)
        if api_key_id is not None:
            ev_query = ev_query.filter(ActivityEvent.api_key_id == api_key_id)
        else:
            ev_query = ev_query.filter(ActivityEvent.api_key_id.is_(None))

        events = ev_query.order_by(desc(ActivityEvent.timestamp)).limit(50).all()

        # Collect unique commit messages and modified projects
        commits = [e for e in events if e.event_type in ["commit", "PushEvent"]]
        commit_messages = list(dict.fromkeys([c.commit_message for c in commits if c.commit_message]))

        active_projects = today_stats.get("active_projects", [])
        top_languages = today_stats.get("top_languages", {})
        coding_time = today_stats.get("active_coding_formatted", "0m")
        commits_count = today_stats.get("commits_today", 0)

        # Build bulleted accomplishments
        accomplishments: List[str] = []
        if commit_messages:
            for msg in commit_messages[:6]:
                accomplishments.append(f"Shipped: {msg}")
        elif active_projects:
            for proj in active_projects:
                accomplishments.append(f"Engineered and refactored core components in `{proj}`")
        else:
            accomplishments.append("Architectural planning, research, and technical design.")

        # Top language summary string
        lang_str = ", ".join([f"{k} ({v})" for k, v in top_languages.items()]) or "Multiple languages"

        # Generate Slack/Discord Markdown formatted text
        date_str = today.strftime("%A, %B %d, %Y")

        markdown_text = (
            f"**Daily Engineering Standup — {date_str}**\n\n"
            f"**Focus Time Today:** {coding_time} | **Commits:** {commits_count} | **Active Workspaces:** {len(active_projects)}\n\n"
            f"**Key Accomplishments & Shipped Work:**\n"
        )
        for acc in accomplishments:
            markdown_text += f"• {acc}\n"

        markdown_text += (
            f"\n**Tech Stack & Languages:**\n"
            f"• {lang_str}\n\n"
            f"**Active Projects:**\n"
            f"• {', '.join(active_projects) if active_projects else 'None'}\n\n"
            f"*Generated autonomously by Velocity Telemetry*"
        )

        return {
            "date": today.isoformat(),
            "active_time": coding_time,
            "commits_count": commits_count,
            "projects": active_projects,
            "top_languages": top_languages,
            "accomplishments": accomplishments,
            "formatted_markdown": markdown_text
        }
