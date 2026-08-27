import os
from fastapi import APIRouter, Request, Query
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["1-Click Installer"])

CLIENT_SCRIPT = '''# Velocity Standalone Zero-Dependency Telemetry Client
# Automatically generated & served by Velocity Cloud
import os
import sys
import time
import json
import urllib.request
import urllib.error
import subprocess
import datetime as dt
from pathlib import Path

CONFIG_DIR = Path.home() / ".velocity"
CONFIG_FILE = CONFIG_DIR / "config.json"

IDE_SIGNATURES = [
    "visual studio code", "vscode", "code", "cursor", "pycharm", "intellij",
    "webstorm", "sublime text", "atom", "android studio", "xcode", "clion",
    "rider", "eclipse", "neovim", "vim", "emacs", "fleet"
]

TERMINAL_SIGNATURES = [
    "terminal", "powershell", "cmd.exe", "command prompt", "git bash",
    "iterm", "alacritty", "kitty", "warp", "wezterm", "hyper"
]

RESEARCH_SIGNATURES = [
    "chrome", "firefox", "edge", "brave", "safari", "arc", "opera",
    "stack overflow", "github", "gitlab", "postman", "insomnia", "chatgpt", "claude"
]

LANG_MAP = {
    ".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "react-ts",
    ".jsx": "react", ".html": "html", ".css": "css", ".rs": "rust", ".go": "go",
    ".java": "java", ".cpp": "cpp", ".c": "c", ".cs": "csharp", ".sql": "sql",
    ".sh": "shell", ".ps1": "powershell", ".json": "json", ".md": "markdown"
}


def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"api_url": "http://127.0.0.1:8000", "api_key": ""}


def save_config(api_url: str, api_key: str):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"api_url": api_url.rstrip("/"), "api_key": api_key}, f, indent=2)


def get_windows_idle_sec() -> float:
    if sys.platform == "win32":
        try:
            import ctypes
            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
            if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
                millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
                return max(0.0, millis / 1000.0)
        except Exception:
            pass
    return 0.0


def get_window_title() -> str:
    if sys.platform == "win32":
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                return buff.value
        except Exception:
            pass
    elif sys.platform == "darwin":
        try:
            cmd = "osascript -e 'tell application \"System Events\" to get name of first process whose frontmost is true'"
            return subprocess.check_output(cmd, shell=True).decode("utf-8").strip()
        except Exception:
            pass
    elif sys.platform.startswith("linux"):
        try:
            cmd = "xdotool getwindowfocus getwindowname"
            return subprocess.check_output(cmd, shell=True).decode("utf-8").strip()
        except Exception:
            pass
    return ""


def parse_context(title: str):
    if not title:
        return "idle", "unknown", "other", ""
    lower = title.lower()
    cat = "general"
    if any(s in lower for s in IDE_SIGNATURES):
        cat = "coding"
    elif any(s in lower for s in TERMINAL_SIGNATURES):
        cat = "terminal"
    elif any(s in lower for s in RESEARCH_SIGNATURES):
        cat = "research"

    proj = "general-dev"
    lang = "other"
    ext = ""
    parts = [p.strip() for p in title.replace("—", "-").replace("•", "-").split("-")]
    if len(parts) >= 2:
        for p in parts:
            if "." in p and not p.startswith("."):
                e = Path(p).suffix.lower()
                if e in LANG_MAP:
                    ext = e
                    lang = LANG_MAP[e]
                    break
        for p in reversed(parts[:-1]):
            clean = p.strip()
            if clean and not any(sig in clean.lower() for sig in IDE_SIGNATURES) and len(clean) < 40:
                proj = clean.replace(" ", "-").lower()
                break
    return cat, proj, lang, ext


def send_heartbeat(api_url: str, api_key: str, proj: str, lang: str, ext: str):
    try:
        url = f"{api_url}/api/v1/ingest/heartbeat"
        payload = json.dumps({
            "project_name": proj or "active-workspace",
            "language": lang or "other",
            "file_extension": ext or "",
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat()
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "x-api-key": api_key
        })
        with urllib.request.urlopen(req, timeout=3) as resp:
            pass
    except Exception:
        pass


def install_global_git(api_url: str, api_key: str):
    try:
        hooks_dir = CONFIG_DIR / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        hook_path = hooks_dir / "post-commit"
        script = f"""#!/bin/sh
API_URL="{api_url}"
API_KEY="{api_key}"
REPO_NAME=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
COMMIT_HASH=$(git rev-parse --short HEAD 2>/dev/null)
COMMIT_MSG=$(git log -1 --pretty=%B 2>/dev/null | tr -d '\\n\\r' | sed 's/"/\\\\"/g')
AUTHOR=$(git log -1 --pretty=%an 2>/dev/null)
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
STATS=$(git diff --shortstat HEAD~1 HEAD 2>/dev/null)
FILES_CHANGED=$(echo "$STATS" | grep -o '[0-9]* file' | cut -d' ' -f1 || echo 0)
INSERTIONS=$(echo "$STATS" | grep -o '[0-9]* insertion' | cut -d' ' -f1 || echo 0)
DELETIONS=$(echo "$STATS" | grep -o '[0-9]* deletion' | cut -d' ' -f1 || echo 0)
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
        with open(hook_path, "w", encoding="utf-8", newline="\\n") as f:
            f.write(script)
        try:
            os.chmod(hook_path, 0o755)
        except Exception:
            pass
        subprocess.run(["git", "config", "--global", "core.hooksPath", str(hooks_dir).replace("\\\\", "/")], check=True)
        print("✅ PC-Wide Global Git Hook Activated.")
    except Exception as e:
        print(f"⚠️  Global Git Hook notice: {e}")


def run_tracker():
    conf = load_config()
    api_url = conf.get("api_url")
    api_key = conf.get("api_key")
    if not api_key:
        print("❌ No API key configured. Run client with setup arguments.")
        return

    print("⚡ Velocity Telemetry Client Running in Background...")
    print(f"📡 Connected to: {api_url}")
    try:
        while True:
            idle_sec = get_windows_idle_sec()
            if idle_sec < 300:
                title = get_window_title()
                cat, proj, lang, ext = parse_context(title)
                if cat in ["coding", "terminal", "research"]:
                    send_heartbeat(api_url, api_key, proj, lang, ext)
            time.sleep(30)
    except KeyboardInterrupt:
        print("\\n🛑 Stopped.")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "setup":
        url = sys.argv[2]
        key = sys.argv[3] if len(sys.argv) > 3 else ""
        save_config(url, key)
        install_global_git(url, key)
        print(f"🎉 Velocity Client setup complete for {url}")
    else:
        run_tracker()
'''


@router.get("/client.py", response_class=PlainTextResponse)
def get_client_script():
    """Serves the standalone, zero-dependency telemetry client script."""
    return PlainTextResponse(CLIENT_SCRIPT, media_type="text/plain")


@router.get("/install.ps1", response_class=PlainTextResponse)
def get_powershell_installer(request: Request, key: str = Query(..., description="Developer API Key")):
    """
    Serves a 1-click Windows PowerShell installer script:
    irm http://.../install.ps1?key=vel_sk_... | iex
    """
    base_url = f"{request.url.scheme}://{request.url.netloc}".rstrip("/")

    ps1_script = f"""# Velocity 1-Click Windows Client Installer
$ErrorActionPreference = "SilentlyContinue"
$ApiUrl = "{base_url}"
$ApiKey = "{key}"

Write-Host "`n⚡ ==================================================" -ForegroundColor Green
Write-Host "   VELOCITY — 1-CLICK PC TELEMETRY SETUP" -ForegroundColor White
Write-Host "==================================================" -ForegroundColor Green
Write-Host "📡 Server: $ApiUrl" -ForegroundColor Cyan
Write-Host "🔑 Key:    $ApiKey" -ForegroundColor Yellow

$VelDir = "$HOME\\.velocity"
if (!(Test-Path $VelDir)) {{
    New-Item -ItemType Directory -Path $VelDir -Force | Out-Null
}}

# Download standalone client script
$ClientFile = "$VelDir\\client.py"
Write-Host "`n⬇️  Downloading standalone client..." -ForegroundColor White
Invoke-WebRequest -Uri "$ApiUrl/client.py" -OutFile $ClientFile -UseBasicParsing

# Run setup and install Global Git Hook
Write-Host "⚙️  Configuring PC-wide global git hook & focus tracker..." -ForegroundColor White
python "$ClientFile" setup "$ApiUrl" "$ApiKey"

# Start background tracker silently
Write-Host "🚀 Launching silent background tracker..." -ForegroundColor Green
Start-Process "pythonw.exe" -ArgumentList "`"$ClientFile`"" -WindowStyle Hidden

Write-Host "`n🎉 SUCCESS! Your PC is now connected to Velocity." -ForegroundColor Green
Write-Host "✨ All coding time, active IDEs, and Git commits will stream to your dashboard automatically!`n" -ForegroundColor White
"""
    return PlainTextResponse(ps1_script, media_type="text/plain")


@router.get("/install.sh", response_class=PlainTextResponse)
def get_bash_installer(request: Request, key: str = Query(..., description="Developer API Key")):
    """
    Serves a 1-click Mac/Linux Bash installer script:
    curl -sSL http://.../install.sh?key=vel_sk_... | bash
    """
    base_url = f"{request.url.scheme}://{request.url.netloc}".rstrip("/")

    sh_script = f"""#!/bin/bash
# Velocity 1-Click Mac/Linux Client Installer
set -e
API_URL="{base_url}"
API_KEY="{key}"

echo ""
echo "⚡ =================================================="
echo "   VELOCITY — 1-CLICK PC TELEMETRY SETUP"
echo "=================================================="
echo "📡 Server: $API_URL"
echo "🔑 Key:    $API_KEY"

VEL_DIR="$HOME/.velocity"
mkdir -p "$VEL_DIR"
CLIENT_FILE="$VEL_DIR/client.py"

echo "⬇️  Downloading standalone client..."
curl -sSL "$API_URL/client.py" -o "$CLIENT_FILE"

echo "⚙️  Configuring PC-wide global git hook & focus tracker..."
python3 "$CLIENT_FILE" setup "$API_URL" "$API_KEY"

echo "🚀 Launching silent background tracker..."
nohup python3 "$CLIENT_FILE" >/dev/null 2>&1 &

echo ""
echo "🎉 SUCCESS! Your PC is now connected to Velocity."
echo "✨ All coding time, active IDEs, and Git commits will stream to your dashboard automatically!"
echo ""
"""
    return PlainTextResponse(sh_script, media_type="text/plain")
