import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, Float, Index, ForeignKey
from app.database import Base


class UserApiKey(Base):
    """Developer API Keys for external clients and apps (OpenAI-style)."""
    __tablename__ = "user_api_keys"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # e.g. "Priya's MacBook", "Rohit's PC"
    key = Column(String(100), unique=True, index=True, nullable=False)  # e.g. "vel_sk_..."
    key_prefix = Column(String(20), nullable=False)  # e.g. "vel_sk_...9a2f"
    total_requests = Column(Integer, default=0)
    rate_limit_per_minute = Column(Integer, default=60)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)


class ActivityEvent(Base):
    """General telemetry event record (file edits, git commits, etc.)."""
    __tablename__ = "activity_events"

    id = Column(Integer, primary_key=True, index=True)
    api_key_id = Column(Integer, nullable=True, index=True)  # User/Tenant isolation ID (None = Admin)
    source = Column(String(50), nullable=False, index=True)  # 'folder_watcher', 'git_hook', 'github', 'manual'
    event_type = Column(String(50), nullable=False, index=True)  # 'file_modified', 'commit', 'branch_switch', 'session'
    project_name = Column(String(100), nullable=False, index=True)
    sanitized_path = Column(String(500), nullable=True)  # sanitized relative path (e.g. "velocity/app/main.py")
    language = Column(String(50), nullable=True, index=True)  # 'python', 'typescript', 'rust', etc.
    metadata_json = Column(JSON, nullable=True)  # sanitized extra data (e.g. lines changed, commit hash)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_activity_user_project_time", "api_key_id", "project_name", "timestamp"),
        Index("ix_activity_user_source_time", "api_key_id", "source", "timestamp"),
    )


class Heartbeat(Base):
    """Presence heartbeat record for computing exact dwell/coding time."""
    __tablename__ = "heartbeats"

    id = Column(Integer, primary_key=True, index=True)
    api_key_id = Column(Integer, nullable=True, index=True)  # User/Tenant isolation ID
    project_name = Column(String(100), nullable=False, index=True)
    language = Column(String(50), nullable=True, index=True)
    file_extension = Column(String(20), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_heartbeat_user_project_time", "api_key_id", "project_name", "timestamp"),
    )


class GitHubEvent(Base):
    """Cached GitHub activity event synced securely from GitHub REST API."""
    __tablename__ = "github_events"

    id = Column(Integer, primary_key=True, index=True)
    api_key_id = Column(Integer, nullable=True, index=True)  # User/Tenant isolation ID
    github_event_id = Column(String(100), unique=True, index=True, nullable=False)
    event_type = Column(String(50), nullable=False, index=True)  # PushEvent, PullRequestEvent, CreateEvent, etc.
    repo_name = Column(String(150), nullable=False, index=True)  # e.g. "octocat/hello-world"
    is_private = Column(Boolean, default=False)
    summary = Column(String(500), nullable=True)
    payload_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, index=True)
