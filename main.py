import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import requests
from requests_oauthlib import OAuth1

try:
    from _version import __version__
except Exception:
    __version__ = "0.0.0"

INSTALL_URL = "https://raw.githubusercontent.com/ryangerardwilson/x/main/install.sh"
LATEST_RELEASE_API = "https://api.github.com/repos/ryangerardwilson/x/releases/latest"


def get_env(name, fallback_name=None):
    value = os.getenv(name)
    if value:
        return value
    if fallback_name:
        return os.getenv(fallback_name)
    return None


def build_auth():
    consumer_key = get_env("X_CONSUMER_KEY", "TWITTER_CONSUMER_KEY")
    consumer_secret = get_env("X_CONSUMER_SECRET", "TWITTER_CONSUMER_SECRET")
    access_token = get_env("X_ACCESS_TOKEN", "TWITTER_ACCESS_TOKEN")
    access_token_secret = get_env("X_ACCESS_TOKEN_SECRET", "TWITTER_ACCESS_TOKEN_SECRET")

    missing = [
        name
        for name, value in [
            ("X_CONSUMER_KEY", consumer_key),
            ("X_CONSUMER_SECRET", consumer_secret),
            ("X_ACCESS_TOKEN", access_token),
            ("X_ACCESS_TOKEN_SECRET", access_token_secret),
        ]
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Missing credentials: "
            + ", ".join(missing)
            + ". Set env vars or their TWITTER_* equivalents."
        )

    return OAuth1(consumer_key, consumer_secret, access_token, access_token_secret)


def post_tweet(text):
    auth = build_auth()
    response = requests.post(
        "https://api.x.com/2/tweets",
        json={"text": text},
        auth=auth,
        timeout=30,
    )

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"X API error {response.status_code}: {response.text.strip()}"
        )

    return response.json()


def build_parser():
    parser = argparse.ArgumentParser(
        description="Post to X from the command line."
    )
    parser.add_argument(
        "text",
        nargs="*",
        help="Post text. If omitted, use -v to open Vim.",
    )
    parser.add_argument(
        "-e",
        "--edit",
        action="store_true",
        help="Open Vim to compose the post.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="store_true",
        help="Show version and exit.",
    )
    parser.add_argument(
        "-u",
        "--upgrade",
        action="store_true",
        help="Upgrade to the latest version.",
    )
    return parser


def _version_tuple(version):
    if not version:
        return (0,)
    version = version.strip()
    if version.startswith("v"):
        version = version[1:]
    parts = []
    for segment in version.split("."):
        digits = ""
        for ch in segment:
            if ch.isdigit():
                digits += ch
            else:
                break
        if digits == "":
            break
        parts.append(int(digits))
    return tuple(parts) if parts else (0,)


def _is_version_newer(candidate, current):
    cand_tuple = _version_tuple(candidate)
    curr_tuple = _version_tuple(current)
    length = max(len(cand_tuple), len(curr_tuple))
    cand_tuple += (0,) * (length - len(cand_tuple))
    curr_tuple += (0,) * (length - len(curr_tuple))
    return cand_tuple > curr_tuple


def _get_latest_version(timeout=5.0):
    try:
        request = Request(LATEST_RELEASE_API, headers={"User-Agent": "x-updater"})
        with urlopen(request, timeout=timeout) as resp:
            data = resp.read().decode("utf-8", errors="replace")
    except (URLError, HTTPError, TimeoutError):
        return None
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return None
    tag = payload.get("tag_name") or payload.get("name")
    if isinstance(tag, str) and tag.strip():
        return tag.strip()
    return None


def _run_upgrade():
    try:
        curl = subprocess.Popen(
            ["curl", "-fsSL", INSTALL_URL],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        print("Upgrade requires curl", file=sys.stderr)
        return 1

    try:
        bash = subprocess.Popen(["bash"], stdin=curl.stdout)
        if curl.stdout is not None:
            curl.stdout.close()
    except FileNotFoundError:
        print("Upgrade requires bash", file=sys.stderr)
        curl.terminate()
        curl.wait()
        return 1

    bash_rc = bash.wait()
    curl_rc = curl.wait()

    if curl_rc != 0:
        stderr = (
            curl.stderr.read().decode("utf-8", errors="replace") if curl.stderr else ""
        )
        if stderr:
            sys.stderr.write(stderr)
        return curl_rc

    return bash_rc


def read_from_vim():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        temp_path = tmp.name

    try:
        while True:
            editor = os.getenv("EDITOR", "vim").strip()
            editor_cmd = shlex.split(editor) if editor else ["vim"]
            if not editor_cmd:
                editor_cmd = ["vim"]
            try:
                subprocess.run(editor_cmd + [temp_path], check=False)
            except FileNotFoundError:
                raise SystemExit(f"Editor not found: {editor_cmd[0]}")
            with open(temp_path, "r", encoding="utf-8") as handle:
                text = handle.read().strip()

            if not text:
                raise SystemExit("No content; cancelled.")

            length = len(text)
            if length <= 280:
                return text

            answer = input(
                f"Draft is {length} chars (limit 280). Re-edit? [y/N] "
            ).strip().lower()
            if answer not in ("y", "yes"):
                raise SystemExit("Cancelled; draft exceeds 280 characters.")
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.version:
        print(__version__)
        return

    if args.upgrade:
        if args.text or args.edit:
            raise SystemExit("Use -u by itself to upgrade.")

        latest = _get_latest_version()
        if latest is None:
            print(
                "Unable to determine latest version; attempting upgrade…",
                file=sys.stderr,
            )
            rc = _run_upgrade()
            sys.exit(rc)

        if (
            __version__
            and __version__ != "0.0.0"
            and not _is_version_newer(latest, __version__)
        ):
            print(f"Already running the latest version ({__version__}).")
            sys.exit(0)

        if __version__ and __version__ != "0.0.0":
            print(f"Upgrading from {__version__} to {latest}…")
        else:
            print(f"Upgrading to {latest}…")
        rc = _run_upgrade()
        sys.exit(rc)

    if args.edit and args.text:
        raise SystemExit("Use either -e or provide text, not both.")

    if args.edit:
        text = read_from_vim()
    else:
        text = " ".join(args.text).strip()

    if not text:
        parser.print_help()
        return

    result = post_tweet(text)
    tweet_id = result.get("data", {}).get("id", "unknown")
    print(f"Posted to X. id={tweet_id}")


if __name__ == "__main__":
    main()
