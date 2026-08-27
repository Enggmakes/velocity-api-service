import sys
import os
import argparse
import httpx
from pathlib import Path

from app.config import settings

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

DEFAULT_API_URL = f"http://{settings.API_HOST}:{settings.API_PORT}"
DEFAULT_API_KEY = settings.API_SECRET_KEY


def show_terminal_status(api_url: str, api_key: str):
    """Display real-time telemetry card directly in terminal."""
    try:
        headers = {"x-api-key": api_key}
        with httpx.Client(timeout=4.0) as client:
            res = client.get(f"{api_url}/api/v1/stats/today", headers=headers)
            if res.status_code != 200:
                print(f"❌ Could not fetch stats from API: {res.status_code} ({res.text})")
                return

            data = res.json()
            is_coding = data.get("is_currently_coding", False)
            status_symbol = "🟢 ACTIVE (Coding)" if is_coding else "⚪ IDLE"
            active_time = data.get("active_coding_formatted", "0m")
            commits = data.get("commits_today", 0)
            events = data.get("total_events", 0)
            projects = ", ".join(data.get("active_projects", [])) or "None"
            langs = ", ".join([f"{k} ({v})" for k, v in data.get("top_languages", {}).items()]) or "None"

            print("\n" + "=" * 50)
            print("       ⚡ PERSONAL TELEMETRY & ACTIVITY ⚡")
            print("=" * 50)
            print(f" Status:             {status_symbol}")
            print(f" Coding Time Today:  {active_time}")
            print(f" Commits Today:      {commits}")
            print(f" Total Events:       {events}")
            print(f" Active Projects:    {projects}")
            print(f" Languages:          {langs}")
            print("=" * 50)
            print(f" 🌐 Dashboard:       {api_url}/dashboard")
            print(f" 📖 API Docs:        {api_url}/docs")
            print("=" * 50 + "\n")
    except Exception as e:
        print(f"❌ Failed to connect to API at {api_url}. Is the server running? ({e})")


def show_standup(api_url: str, api_key: str):
    """Generate and display today's AI engineering standup."""
    try:
        headers = {"x-api-key": api_key}
        with httpx.Client(timeout=6.0) as client:
            res = client.get(f"{api_url}/api/v1/analytics/standup", headers=headers)
            if res.status_code != 200:
                print(f"❌ Could not generate standup: {res.status_code} ({res.text})")
                return

            data = res.json()
            print("\n" + data.get("formatted_markdown", ""))
            print("\n📋 Ready to copy into Slack / Discord / Notion!\n")
    except Exception as e:
        print(f"❌ Failed to connect to API at {api_url}: {e}")


def run_client_setup(api_url: str, api_key: str):
    """1-Click setup of global git hook and local config."""
    print("\n⚡ Velocity 1-Click Client Setup")
    print(f"📡 Connecting to: {api_url}")
    print(f"🔑 API Key:       {api_key[:12]}...")

    # 1. Test connection
    try:
        headers = {"x-api-key": api_key}
        with httpx.Client(timeout=5.0) as client:
            res = client.get(f"{api_url}/api/v1/stats/today", headers=headers)
            if res.status_code == 200:
                print("✅ API connection verified successfully!")
            else:
                print(f"⚠️ Warning: Server returned status {res.status_code}. Proceeding with local setup...")
    except Exception as e:
        print(f"⚠️ Warning: Could not ping server ({e}). Proceeding with local setup...")

    # 2. Install PC-wide Global Git Hook
    from collectors.git_hook_installer import install_global_git_hook
    install_global_git_hook(api_url, api_key)

    print("\n🎉 Setup complete! You can now start the active window tracker with:")
    print(f"   python cli.py window-track --url {api_url} --key {api_key}\n")


def main():
    parser = argparse.ArgumentParser(description="Personal Activity & Telemetry CLI")
    parser.add_argument("--key", default=DEFAULT_API_KEY, help="API Key for authentication")
    parser.add_argument("--url", default=DEFAULT_API_URL, help="API Server URL")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status
    subparsers.add_parser("status", help="Show today's technical activity in the terminal")

    # Standup
    subparsers.add_parser("standup", help="Generate AI daily engineering standup report")

    # Active Window & Focus Tracker
    window_parser = subparsers.add_parser("window-track", help="Start passive active window & idle focus tracker")
    window_parser.add_argument("--interval", type=int, default=30, help="Check interval in seconds (default: 30)")

    # Watch folder
    watch_parser = subparsers.add_parser("watch", help="Start folder watcher daemon")
    watch_parser.add_argument("folder", nargs="?", default=".", help="Folder path to monitor (default: current directory)")

    # Git Hook (Repo specific)
    hook_parser = subparsers.add_parser("git-hook", help="Install git post-commit telemetry hook for target repo")
    hook_parser.add_argument("repo", nargs="?", default=".", help="Target Git repository path")

    # Git Global Hook (PC-wide)
    subparsers.add_parser("git-global", help="Install PC-wide global git post-commit hook for ALL repos")

    # Client Setup
    subparsers.add_parser("client-setup", help="1-Click client configuration for this PC")

    # GitHub Sync
    subparsers.add_parser("sync-github", help="Sync GitHub events")

    # Run Server
    subparsers.add_parser("server", help="Start the Telemetry FastAPI server")

    args = parser.parse_args()

    api_key = args.key or DEFAULT_API_KEY
    api_url = (args.url or DEFAULT_API_URL).rstrip("/")

    if args.command == "status" or args.command is None:
        show_terminal_status(api_url, api_key)
    elif args.command == "standup":
        show_standup(api_url, api_key)
    elif args.command == "window-track":
        from collectors.window_tracker import start_window_tracker
        start_window_tracker(api_url=api_url, api_key=api_key, interval=args.interval)
    elif args.command == "git-global":
        from collectors.git_hook_installer import install_global_git_hook
        install_global_git_hook(api_url=api_url, api_key=api_key)
    elif args.command == "client-setup":
        run_client_setup(api_url, api_key)
    elif args.command == "watch":
        from collectors.folder_watcher import start_watcher
        start_watcher(args.folder, api_url=api_url, api_key=api_key)
    elif args.command == "git-hook":
        from collectors.git_hook_installer import install_git_hook
        install_git_hook(args.repo, api_url=api_url, api_key=api_key)
    elif args.command == "sync-github":
        from collectors.github_syncer import sync_github_activity
        sync_github_activity()
    elif args.command == "server":
        import uvicorn
        print(f"🚀 Starting Personal Telemetry API on http://{settings.API_HOST}:{settings.API_PORT}...")
        uvicorn.run("app.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)


if __name__ == "__main__":
    main()
