import datetime
from fastapi import APIRouter, Depends, HTTPException, Security, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import ActivityEvent, Heartbeat, GitHubEvent
from app.schemas import HeartbeatCreate, FileEventCreate, BatchFileEventCreate, GitCommitCreate
from app.services.sanitizer import PrivacySanitizer
from app.services.auth_service import verify_api_key

router = APIRouter(prefix="/api/v1", tags=["Ingest & Telemetry"])


@router.post("/ingest/heartbeat", summary="Record a coding presence heartbeat")
def ingest_heartbeat(
    payload: HeartbeatCreate,
    db: Session = Depends(get_db),
    auth: dict = Depends(verify_api_key)
):
    """
    Heartbeat endpoint called by the local folder watcher / editor.
    Used to compute precise active dwell time and active projects per user.
    """
    event_time = payload.timestamp or datetime.datetime.utcnow()
    api_key_id = auth.get("key_id")

    hb = Heartbeat(
        api_key_id=api_key_id,
        project_name=payload.project_name.strip(),
        language=payload.language,
        file_extension=payload.file_extension,
        timestamp=event_time
    )
    db.add(hb)
    db.commit()

    return {"status": "success", "message": "Heartbeat recorded"}


@router.post("/ingest/file-event", summary="Record a local file modification event (sanitized)")
def ingest_file_event(
    payload: FileEventCreate,
    db: Session = Depends(get_db),
    auth: dict = Depends(verify_api_key)
):
    """
    Record a single file event. Path is automatically sanitized and privacy filtered.
    Sensitive files (.env, keys) are dropped automatically.
    """
    sanitized_path, lang, ext = PrivacySanitizer.sanitize_path(payload.raw_path, payload.project_name)
    if not sanitized_path:
        return {"status": "ignored", "reason": "Path ignored by privacy filter or sensitive pattern."}

    event_time = payload.timestamp or datetime.datetime.utcnow()
    api_key_id = auth.get("key_id")

    event = ActivityEvent(
        api_key_id=api_key_id,
        source="folder_watcher",
        event_type=payload.event_type,
        project_name=payload.project_name,
        sanitized_path=sanitized_path,
        language=lang,
        metadata_json={
            "lines_added": payload.lines_added,
            "lines_deleted": payload.lines_deleted,
            "extension": ext
        },
        timestamp=event_time
    )
    db.add(event)

    # Also log a presence heartbeat
    hb = Heartbeat(
        api_key_id=api_key_id,
        project_name=payload.project_name,
        language=lang,
        file_extension=ext,
        timestamp=event_time
    )
    db.add(hb)

    db.commit()
    return {"status": "success", "sanitized_path": sanitized_path}


@router.post("/ingest/batch-file-events", summary="Batch record multiple file events")
def ingest_batch_file_events(
    payload: BatchFileEventCreate,
    db: Session = Depends(get_db),
    auth: dict = Depends(verify_api_key)
):
    """Ingest a batch of file modification events from the watcher daemon."""
    recorded_count = 0
    now = datetime.datetime.utcnow()
    api_key_id = auth.get("key_id")

    for item in payload.events:
        sanitized_path, lang, ext = PrivacySanitizer.sanitize_path(item.raw_path, item.project_name)
        if not sanitized_path:
            continue

        event_time = item.timestamp or now
        event = ActivityEvent(
            api_key_id=api_key_id,
            source="folder_watcher",
            event_type=item.event_type,
            project_name=item.project_name,
            sanitized_path=sanitized_path,
            language=lang,
            metadata_json={"lines_added": item.lines_added, "lines_deleted": item.lines_deleted, "extension": ext},
            timestamp=event_time
        )
        db.add(event)
        recorded_count += 1

    db.commit()
    return {"status": "success", "recorded_count": recorded_count}


@router.post("/ingest/git-commit", summary="Record a local Git post-commit hook event")
def ingest_git_commit(
    payload: GitCommitCreate,
    db: Session = Depends(get_db),
    auth: dict = Depends(verify_api_key)
):
    """Endpoint triggered by Git post-commit hooks."""
    event_time = payload.timestamp or datetime.datetime.utcnow()
    api_key_id = auth.get("key_id")

    event = ActivityEvent(
        api_key_id=api_key_id,
        source="git_hook",
        event_type="commit",
        project_name=payload.project_name,
        sanitized_path=None,
        language=None,
        metadata_json={
            "commit_hash": payload.commit_hash,
            "commit_message": payload.commit_message,
            "author": payload.author_name,
            "files_changed": payload.files_changed,
            "insertions": payload.insertions,
            "deletions": payload.deletions
        },
        timestamp=event_time
    )
    db.add(event)

    # Log heartbeat for the commit
    hb = Heartbeat(
        api_key_id=api_key_id,
        project_name=payload.project_name,
        language="git",
        file_extension=".git",
        timestamp=event_time
    )
    db.add(hb)

    db.commit()
    return {"status": "success", "commit_hash": payload.commit_hash}
