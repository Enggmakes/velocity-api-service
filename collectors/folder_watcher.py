import os
import sys
import time
import datetime as dt
import argparse
import httpx
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

DEFAULT_API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
DEFAULT_API_KEY = os.getenv("API_SECRET_KEY", "my_secure_telemetry_key_9f8d7e6c5b4a321")

IGNORED_PATTERNS = [
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".idea", ".vscode",
    ".env", ".pem", ".key", "data/telemetry.db", ".tmp", ".log"
]


class WorkspaceChangeHandler(FileSystemEventHandler):
    """Watches local file modifications and posts sanitized telemetry to the local API."""

    def __init__(self, workspace_path: str, api_url: str, api_key: str):
        self.workspace_path = os.path.abspath(workspace_path)
        self.project_name = Path(self.workspace_path).name
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.last_sent_times = {}
        self.debounce_seconds = 3.0  # Prevent spamming on rapid keystrokes

    def should_ignore(self, path: str) -> bool:
        norm = path.replace("\\", "/").lower()
        return any(pattern in norm for pattern in IGNORED_PATTERNS)

    def on_modified(self, event):
        if event.is_directory or self.should_ignore(event.src_path):
            return

        now = time.time()
        last_time = self.last_sent_times.get(event.src_path, 0)
        if now - last_time < self.debounce_seconds:
            return

        self.last_sent_times[event.src_path] = now
        self.send_event(event.src_path, "file_modified")

    def on_created(self, event):
        if event.is_directory or self.should_ignore(event.src_path):
            return
        self.send_event(event.src_path, "file_created")

    def get_project_name(self, filepath: str) -> str:
        try:
            rel = os.path.relpath(filepath, self.workspace_path)
            parts = rel.replace("\\", "/").split("/")
            if len(parts) > 1:
                return parts[0]
        except Exception:
            pass
        return self.project_name

    def send_event(self, filepath: str, event_type: str):
        try:
            proj_name = self.get_project_name(filepath)
            payload = {
                "project_name": proj_name,
                "raw_path": filepath,
                "event_type": event_type,
                "lines_added": 0,
                "lines_deleted": 0,
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat()
            }
            headers = {"x-api-key": self.api_key}
            with httpx.Client(timeout=3.0) as client:
                res = client.post(f"{self.api_url}/api/v1/ingest/file-event", json=payload, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("status") == "success":
                        print(f"⚡ [Tracked] {proj_name} -> {data.get('sanitized_path')}")
        except Exception:
            pass


def start_watcher(watch_directory: str, api_url: str = DEFAULT_API_URL, api_key: str = DEFAULT_API_KEY):
    """Start watching directory for changes."""
    abs_dir = os.path.abspath(watch_directory)
    print(f"🛡️  Starting Privacy-First Folder Watcher on: {abs_dir}")
    print(f"📡  Reporting to: {api_url}")
    print(f"🔑  Using Key: {api_key[:10]}...{api_key[-4:] if len(api_key)>14 else ''}")
    print("Press Ctrl+C to stop.\n")

    event_handler = WorkspaceChangeHandler(abs_dir, api_url=api_url, api_key=api_key)
    observer = Observer()
    observer.schedule(event_handler, path=abs_dir, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n🛑 Watcher stopped.")
    observer.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Telemetry Folder Watcher")
    parser.add_argument("folder", nargs="?", default=".", help="Folder to watch")
    parser.add_argument("--key", default=DEFAULT_API_KEY, help="API Key for tenant/user")
    parser.add_argument("--url", default=DEFAULT_API_URL, help="API Server URL")
    args = parser.parse_args()

    start_watcher(args.folder, api_url=args.url, api_key=args.key)
