import os


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


__version__ = _version_from_env() or DEV_VERSION
