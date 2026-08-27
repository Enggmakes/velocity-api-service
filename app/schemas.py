import datetime
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field


# Ingestion Models
class HeartbeatCreate(BaseModel):
    project_name: str = Field(..., description="Name of the active workspace or project")
    language: Optional[str] = Field(None, description="Programming language (e.g. python, typescript)")
    file_extension: Optional[str] = Field(None, description="File extension (e.g. .py, .tsx)")
    timestamp: Optional[datetime.datetime] = Field(None, description="Event timestamp (defaults to now)")


class FileEventCreate(BaseModel):
    project_name: str = Field(..., description="Name of the project")
    raw_path: str = Field(..., description="File path (will be automatically sanitized and stripped of user paths)")
    event_type: str = Field("file_modified", description="file_created, file_modified, file_deleted")
    lines_added: Optional[int] = Field(0, description="Estimated lines added")
    lines_deleted: Optional[int] = Field(0, description="Estimated lines deleted")
    timestamp: Optional[datetime.datetime] = Field(None, description="Event timestamp")


class BatchFileEventCreate(BaseModel):
    events: List[FileEventCreate]


class GitCommitCreate(BaseModel):
    project_name: str = Field(..., description="Project / Repo name")
    commit_hash: str = Field(..., description="Short commit SHA")
    commit_message: str = Field(..., description="Commit message")
    author_name: Optional[str] = Field(None, description="Author name")
    files_changed: Optional[int] = Field(0, description="Number of changed files")
    insertions: Optional[int] = Field(0, description="Number of insertions")
    deletions: Optional[int] = Field(0, description="Number of deletions")
    timestamp: Optional[datetime.datetime] = Field(None, description="Commit timestamp")


# Response Models
class ActivityResponse(BaseModel):
    id: int
    source: str
    event_type: str
    project_name: str
    sanitized_path: Optional[str]
    language: Optional[str]
    metadata_json: Optional[Dict[str, Any]]
    timestamp: datetime.datetime

    model_config = {"from_attributes": True}


class TodayStatsResponse(BaseModel):
    date: str
    active_coding_seconds: int
    active_coding_formatted: str
    total_events: int
    commits_today: int
    active_projects: List[str]
    top_languages: Dict[str, int]
    is_currently_coding: bool
    last_activity_ago_minutes: Optional[int]
    tenant_name: Optional[str] = None


class ProjectMetricsResponse(BaseModel):
    project_name: str
    total_active_seconds: int
    total_active_formatted: str
    total_events: int
    total_commits: int
    last_active: Optional[datetime.datetime]
    top_languages: List[str]


class PublicStatusResponse(BaseModel):
    status: str  # "online", "coding", "idle"
    current_activity_category: str  # e.g., "Web Development", "Backend Engineering" (no sensitive project names)
    active_hours_today: float
    commits_today: int
    top_languages: List[str]
    last_updated: datetime.datetime


# Developer API Key Management Schemas (OpenAI-style)
class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Name or label for this API key (e.g. My Website)")
    rate_limit_per_minute: Optional[int] = Field(60, ge=1, le=1000, description="Max requests per minute")


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    total_requests: int
    rate_limit_per_minute: int
    is_active: bool
    created_at: datetime.datetime
    last_used_at: Optional[datetime.datetime]

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(BaseModel):
    id: int
    name: str
    key: str  # Secret key returned only ONCE upon creation
    key_prefix: str
    message: str = "Please copy your secret API key now. You will not be able to see it again!"

