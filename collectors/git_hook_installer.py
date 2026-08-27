import os
import sys
import subprocess
from pathlib import Path

DEFAULT_API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
DEFAULT_API_KEY = os.getenv("API_SECRET_KEY", "my_secure_telemetry_key_9f8d7e6c5b4a321")


def generate_hook_script(api_url: str = DEFAULT_API_URL, api_key: str = DEFAULT_API_KEY) -> str:
    clean_url = api_url.rstrip("/")
    return f"""#!/bin/sh
# Velocity Telemetry - PC-Wide Global Git Post Commit Hook

API_URL="{clean_url}"
API_KEY="{api_key}"

# 1. Get Repository Name
REPO_NAME=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")

# 2. Get Commit Metadata
COMMIT_HASH=$(git rev-parse --short HEAD 2>/dev/null)
COMMIT_MSG=$(git log -1 --pretty=%B 2>/dev/null | tr -d '\\n\\r' | sed 's/"/\\\\"/g')
AUTHOR=$(git log -1 --pretty=%an 2>/dev/null)
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)

# 3. Get diff stats
STATS=$(git diff --shortstat HEAD~1 HEAD 2>/dev/null)
FILES_CHANGED=$(echo "$STATS" | grep -o '[0-9]* file' | cut -d' ' -f1 || echo 0)
INSERTIONS=$(echo "$STATS" | grep -o '[0-9]* insertion' | cut -d' ' -f1 || echo 0)
DELETIONS=$(echo "$STATS" | grep -o '[0-9]* deletion' | cut -d' ' -f1 || echo 0)

# 4. Asynchronously send telemetry event
curl -s -X POST "$API_URL/api/v1/ingest/git-commit" \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: $API_KEY" \\
  -d '{{
    "project_name": "'"$REPO_NAME"'",
    "commit_hash": "'"$COMMIT_HASH"'",
    "commit_message": "'"$COMMIT_MSG"'",
    "author_name": "'"$AUTHOR"'",
    "branch_name": "'"$BRANCH"'",
    "files_changed": '"${{FILES_CHANGED:-0}}"',
    "insertions": '"${{INSERTIONS:-0}}"',
    "deletions": '"${{DELETIONS:-0}}"'
  }}' >/dev/null 2>&1 &
"""


def install_global_git_hook(api_url: str = DEFAULT_API_URL, api_key: str = DEFAULT_API_KEY) -> bool:
    """
    Install a PC-wide Global Git Hook using `git config --global core.hooksPath`.
    Tracks EVERY git commit across all repositories on this computer.
    """
    try:
        home_dir = Path.home()
        global_hooks_dir = home_dir / ".velocity" / "hooks"
        global_hooks_dir.mkdir(parents=True, exist_ok=True)
        hook_file = global_hooks_dir / "post-commit"

        hook_content = generate_hook_script(api_url, api_key)
        with open(hook_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(hook_content)

        try:
            os.chmod(hook_file, 0o755)
        except Exception:
            pass

        # Set git global hooks path
        hooks_path_str = str(global_hooks_dir).replace("\\", "/")
        subprocess.run(["git", "config", "--global", "core.hooksPath", hooks_path_str], check=True)

        print("=" * 60)
        print("🌐 PC-WIDE GLOBAL GIT HOOK INSTALLED SUCCESSFULLY")
        print("=" * 60)
        print(f"📁 Global Hooks Dir: {global_hooks_dir}")
        print(f"📡 Reporting to:     {api_url}")
        print("✨ Every git commit in ANY project on this PC will now automatically stream to Velocity!")
        print("=" * 60)
        return True
    except Exception as e:
        print(f"❌ Failed to install global git hook: {e}")
        return False


def install_git_hook(repo_path: str = ".", api_url: str = DEFAULT_API_URL, api_key: str = DEFAULT_API_KEY) -> bool:
    """Install post-commit hook into a single specific Git repository."""
    repo_dir = Path(repo_path).resolve()
    git_dir = repo_dir / ".git"

    if not git_dir.exists():
        print(f"❌ Error: {repo_dir} is not a git repository (missing .git directory).")
        return False

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    hook_file = hooks_dir / "post-commit"

    with open(hook_file, "w", encoding="utf-8", newline="\n") as f:
        f.write(generate_hook_script(api_url, api_key))

    try:
        os.chmod(hook_file, 0o755)
    except Exception:
        pass

    print(f"✅ Telemetry Git Post-Commit hook installed for repo: {repo_dir.name}")
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--global":
        install_global_git_hook()
    else:
        target = sys.argv[1] if len(sys.argv) > 1 else "."
        install_git_hook(target)
