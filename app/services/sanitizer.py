import os
import re
from pathlib import Path
from typing import Tuple, Optional
from app.config import settings

LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "react",
    ".tsx": "react-ts",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
    ".sql": "sql",
    ".sh": "shell",
    ".ps1": "powershell",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".dockerfile": "docker",
    "dockerfile": "docker"
}


class PrivacySanitizer:
    """Zero-leak path sanitizer and privacy validator."""

    @staticmethod
    def is_sensitive(path_str: str) -> bool:
        """Check if a file path contains sensitive information (keys, env files, tokens)."""
        lower_path = path_str.lower().replace("\\", "/")
        filename = Path(lower_path).name

        # Check against sensitive file patterns
        for pattern in settings.SENSITIVE_PATTERNS:
            if pattern in filename or lower_path.endswith(pattern):
                return True

        # Check for common credential keywords in file name
        if any(k in filename for k in ["secret", "credential", "password", "token", "private_key"]):
            return True

        return False

    @staticmethod
    def is_ignored_directory(path_str: str) -> bool:
        """Check if path is inside an ignored directory like node_modules or .git."""
        normalized = path_str.replace("\\", "/").lower()
        parts = normalized.split("/")
        return any(ignored in parts for ignored in settings.IGNORED_DIRECTORIES)

    @staticmethod
    def sanitize_path(raw_path: str, project_name: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Sanitize an absolute path:
        1. Strips out C:\\Users\\... or D:\\SOURCE CODE\\...
        2. Returns (sanitized_path, language, extension) or (None, None, None) if blocked.
        """
        if not raw_path:
            return None, None, None

        # Check for sensitive patterns
        if PrivacySanitizer.is_sensitive(raw_path) or PrivacySanitizer.is_ignored_directory(raw_path):
            return None, None, None

        # Normalize slashes
        normalized = raw_path.replace("\\", "/")

        # Strip workspace root if defined
        if settings.WORKSPACE_ROOT:
            ws_root_norm = settings.WORKSPACE_ROOT.replace("\\", "/").rstrip("/")
            if normalized.lower().startswith(ws_root_norm.lower()):
                normalized = normalized[len(ws_root_norm):].lstrip("/")

        # Strip user home directory if present
        home_path = str(Path.home()).replace("\\", "/").rstrip("/")
        if normalized.lower().startswith(home_path.lower()):
            normalized = normalized[len(home_path):].lstrip("/")

        # Remove drive letters (e.g. "C:/", "D:/")
        normalized = re.sub(r"^[a-zA-Z]:/", "", normalized)

        # Ensure project prefix if not already present
        if project_name and not normalized.startswith(project_name):
            sanitized = f"{project_name}/{normalized.lstrip('/')}"
        else:
            sanitized = normalized

        # Extract file extension and language
        path_obj = Path(sanitized)
        ext = path_obj.suffix.lower()
        lang = LANGUAGE_EXTENSIONS.get(ext) or LANGUAGE_EXTENSIONS.get(path_obj.name.lower(), "other")

        return sanitized, lang, ext
