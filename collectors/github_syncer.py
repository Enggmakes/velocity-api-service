import os
import sys
import httpx
from datetime import datetime

from app.config import settings
from app.database import SessionLocal
from app.models import ActivityEvent, GitHubEvent, Heartbeat


def sync_github_activity():
    """
    Fetch recent GitHub public and private events for the configured user.
    Stores commit and PR events with sanitized metadata.
    """
    username = settings.GITHUB_USERNAME
    token = settings.GITHUB_PAT

    if not username:
        print("⚠️  No GITHUB_USERNAME set in .env. Skipping GitHub sync.")
        return {"status": "skipped", "reason": "No GITHUB_USERNAME configured"}

    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    url = f"https://api.github.com/users/{username}/events"
    print(f"🔄 Syncing GitHub events for user: {username}...")

    try:
        with httpx.Client(timeout=10.0) as client:
            res = client.get(url, headers=headers)
            if res.status_code != 200:
                print(f"❌ GitHub API Error: {res.status_code} - {res.text}")
                return {"status": "error", "code": res.status_code}

            events = res.json()
            db = SessionLocal()
            synced_count = 0

            for ev in events:
                event_id = str(ev.get("id"))
                event_type = ev.get("type")
                repo_info = ev.get("repo", {})
                repo_name = repo_info.get("name", "unknown")
                created_at_str = ev.get("created_at")
                created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00")) if created_at_str else datetime.utcnow()

                # Check if already synced
                exists = db.query(GitHubEvent).filter(GitHubEvent.github_event_id == event_id).first()
                if exists:
                    continue

                # Build summary & metadata
                payload = ev.get("payload", {})
                summary = f"{event_type} on {repo_name}"
                if event_type == "PushEvent":
                    commits = payload.get("commits", [])
                    summary = f"Pushed {len(commits)} commit(s) to {repo_name}"
                elif event_type == "PullRequestEvent":
                    action = payload.get("action", "")
                    summary = f"PR {action} on {repo_name}"

                # Store in GitHubEvents table
                gh_record = GitHubEvent(
                    github_event_id=event_id,
                    event_type=event_type,
                    repo_name=repo_name,
                    is_private=not ev.get("public", True),
                    summary=summary,
                    payload_json=payload,
                    created_at=created_at
                )
                db.add(gh_record)

                # Also insert as general ActivityEvent
                activity = ActivityEvent(
                    source="github",
                    event_type=event_type,
                    project_name=repo_name.split("/")[-1],
                    sanitized_path=None,
                    language=None,
                    metadata_json={"github_event_id": event_id, "summary": summary},
                    timestamp=created_at
                )
                db.add(activity)

                # Presence heartbeat
                hb = Heartbeat(
                    project_name=repo_name.split("/")[-1],
                    language="github",
                    file_extension=None,
                    timestamp=created_at
                )
                db.add(hb)

                synced_count += 1

            db.commit()
            db.close()

            print(f"✅ Successfully synced {synced_count} new GitHub events.")
            return {"status": "success", "new_events_synced": synced_count}

    except Exception as e:
        print(f"❌ Error during GitHub sync: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    sync_github_activity()
