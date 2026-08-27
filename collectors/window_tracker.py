import os
import sys
import time
import datetime as dt
import httpx
from pathlib import Path

DEFAULT_API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
DEFAULT_API_KEY = os.getenv("API_SECRET_KEY", "my_secure_telemetry_key_9f8d7e6c5b4a321")
IDLE_THRESHOLD_SECONDS = 300  # 5 minutes of no keyboard/mouse activity = Idle

# Known IDE and Editor application signatures
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


def get_windows_idle_duration_seconds() -> float:
    """Returns idle duration in seconds on Windows using Win32 API."""
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


def get_active_window_title() -> str:
    """Gets the active window title cross-platform."""
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
            import subprocess
            cmd = "osascript -e 'tell application \"System Events\" to get name of first process whose frontmost is true'"
            return subprocess.check_output(cmd, shell=True).decode("utf-8").strip()
        except Exception:
            pass
    elif sys.platform.startswith("linux"):
        try:
            import subprocess
            cmd = "xdotool getwindowfocus getwindowname"
            return subprocess.check_output(cmd, shell=True).decode("utf-8").strip()
        except Exception:
            pass
    return ""


def parse_window_context(window_title: str):
    """
    Classify window context and extract project name, language, and category.
    Example title: 'main.py - velocity - Visual Studio Code'
    """
    if not window_title:
        return "idle", "unknown", "other", ""

    lower_title = window_title.lower()
    
    # 1. Classify Activity Category
    category = "general"
    if any(ide in lower_title for ide in IDE_SIGNATURES):
        category = "coding"
    elif any(term in lower_title for term in TERMINAL_SIGNATURES):
        category = "terminal"
    elif any(res in lower_title for res in RESEARCH_SIGNATURES):
        category = "research"

    # 2. Extract Project & File Info
    project_name = "general-dev"
    language = "other"
    file_extension = ""

    # Common separator in IDE titles is ' - ' or ' — '
    parts = [p.strip() for p in window_title.replace("—", "-").replace("•", "-").split("-")]
    
    if len(parts) >= 2:
        # Check for filename with extension
        for part in parts:
            if "." in part and not part.startswith("."):
                possible_file = part.strip()
                ext = Path(possible_file).suffix.lower()
                if ext in [".py", ".ts", ".js", ".tsx", ".jsx", ".rs", ".go", ".java", ".cpp", ".c", ".html", ".css", ".sql", ".sh"]:
                    file_extension = ext
                    from app.services.sanitizer import LANGUAGE_EXTENSIONS
                    language = LANGUAGE_EXTENSIONS.get(ext, "other")
                    break

        # Project name is usually one of the middle parts before the IDE name
        for part in reversed(parts[:-1]):
            clean_part = part.strip()
            if clean_part and not any(sig in clean_part.lower() for sig in IDE_SIGNATURES) and len(clean_part) < 40:
                project_name = clean_part.replace(" ", "-").lower()
                break

    return category, project_name, language, file_extension


class ActiveWindowTracker:
    """Passive focus and active window tracker with zero-risk local telemetry."""

    def __init__(self, api_url: str = DEFAULT_API_URL, api_key: str = DEFAULT_API_KEY, check_interval: int = 30):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.check_interval = check_interval
        self.running = False

    def send_heartbeat(self, project_name: str, language: str, file_ext: str, category: str):
        try:
            payload = {
                "project_name": project_name or "active-workspace",
                "language": language or "other",
                "file_extension": file_ext or "",
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat()
            }
            headers = {"x-api-key": self.api_key}
            with httpx.Client(timeout=3.0) as client:
                client.post(f"{self.api_url}/api/v1/ingest/heartbeat", json=payload, headers=headers)
        except Exception:
            pass

    def start(self):
        self.running = True
        print(f"👁️  Active Window & Focus Tracker running...")
        print(f"📡  Reporting to: {self.api_url}")
        print(f"⏱️  Checking every {self.check_interval}s | Idle timeout: {IDLE_THRESHOLD_SECONDS}s")

        try:
            while self.running:
                idle_sec = get_windows_idle_duration_seconds() if sys.platform == "win32" else 0.0

                if idle_sec >= IDLE_THRESHOLD_SECONDS:
                    # User is away from keyboard
                    pass
                else:
                    title = get_active_window_title()
                    category, project, lang, ext = parse_window_context(title)

                    if category in ["coding", "terminal", "research"]:
                        self.send_heartbeat(project, lang, ext, category)

                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            print("\n🛑 Window tracker stopped.")


def start_window_tracker(api_url: str = DEFAULT_API_URL, api_key: str = DEFAULT_API_KEY, interval: int = 30):
    tracker = ActiveWindowTracker(api_url=api_url, api_key=api_key, check_interval=interval)
    tracker.start()


if __name__ == "__main__":
    start_window_tracker()
