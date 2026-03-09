import os
import subprocess
from pathlib import Path


DEV_VERSION = "0.0.0-dev"


def _normalize_version(raw):
    value = (raw or "").strip()
    if not value:
        return ""
    return value[1:] if value.startswith("v") else value


def _version_from_env():
    for name in ("APP_VERSION", "VERSION", "GITHUB_REF_NAME"):
        value = _normalize_version(os.getenv(name))
        if value:
            return value
    return ""


def _version_from_git():
    repo_dir = Path(__file__).resolve().parent
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--dirty=-dirty"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, OSError):
        return ""
    return _normalize_version(result.stdout)


__version__ = _version_from_env() or _version_from_git() or DEV_VERSION
