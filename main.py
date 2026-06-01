import base64
import json
import mimetypes
import os
import shlex
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from _version import __version__

MEDIA_CHUNK_SIZE = 4 * 1024 * 1024
MEDIA_UPLOAD_RETRIES = 8
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
ANSI_GRAY = "\033[38;5;245m"
ANSI_RESET = "\033[0m"
INSTALL_SCRIPT = Path(__file__).resolve().with_name("install.sh")
INSTALL_SCRIPT_URL = "https://raw.githubusercontent.com/ryangerardwilson/x/main/install.sh"
HELP_TEXT = """X CLI
publish to X and manage reply workflows from the terminal

global actions:
  x help
    show this help
  x version
    print the installed version
  x upgrade
    upgrade to the latest release

features:
  publish text directly
  # x post <text>
  x post "ship the patch"

  publish with media
  # x post <text> with media <path>
  x post "ship the patch" with media ~/media/demo.mp4

  compose in the editor resolved from $VISUAL, then $EDITOR, then vim
  # x post in editor [with media <path>]
  x post in editor
  x post in editor with media ~/media/demo.mp4

  validate OAuth2 auth or force token refresh
  # x auth check | x auth refresh
  x auth check
  x auth refresh

  list bookmarked posts for reply workflows
  # x bookmarks list [json] [limit <count>]
  x bookmarks list
  x bookmarks list json limit 20

  remove a bookmark after you have handled it
  # x bookmarks remove <tweet_id>
  x bookmarks remove 1894451234567890123

  post a reply to a bookmarked post
  # x reply to <tweet_id> body <text> | x reply to <tweet_id> in editor
  x reply to 1894451234567890123 body "The useful test is whether it survives contact with ops."
  x reply to 1894451234567890123 in editor
"""


class _HttpResponse:
    def __init__(self, status_code, headers, body_bytes):
        self.status_code = status_code
        self.headers = headers
        self._body = body_bytes
        self.text = body_bytes.decode("utf-8", errors="replace")

    def json(self):
        return json.loads(self.text)


def _default_oauth2_token_file():
    data_home = os.getenv("XDG_DATA_HOME")
    if data_home:
        base = os.path.expanduser(data_home)
    else:
        base = os.path.expanduser("~/.local/share")
    return os.path.join(base, "x", "tokens", "oauth2_token.json")


def get_env(name, fallback_name=None):
    value = os.getenv(name)
    if value:
        return value
    if fallback_name:
        return os.getenv(fallback_name)
    return None


def _requests_module():
    import requests

    return requests


def _xdk_symbols():
    try:
        from xdk import Client as XdkClient
        from xdk.media.models import (
            AppendUploadRequest,
            InitializeUploadRequest,
            UploadRequest,
        )
        from xdk.posts.models import CreateRequest, CreateRequestMedia, CreateRequestReply
    except ImportError:
        return None
    return (
        XdkClient,
        AppendUploadRequest,
        InitializeUploadRequest,
        UploadRequest,
        CreateRequest,
        CreateRequestMedia,
        CreateRequestReply,
    )


def _oauth2_pkce_auth_class():
    try:
        from xdk.oauth2_auth import OAuth2PKCEAuth
    except ImportError:
        return None
    return OAuth2PKCEAuth


def _urllib_parse():
    import urllib.parse

    return urllib.parse


def _urllib_request_symbols():
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen

    return Request, urlopen, HTTPError, URLError


def _oauth2_token_file_path():
    token_file = (
        get_env("X_OAUTH2_TOKEN_FILE", "TWITTER_OAUTH2_TOKEN_FILE")
        or _default_oauth2_token_file()
    )
    return os.path.expanduser(token_file)


def _build_oauth2_auth(payload):
    OAuth2PKCEAuth = _oauth2_pkce_auth_class()
    if OAuth2PKCEAuth is None:
        raise RuntimeError("Missing dependency: xdk. Install requirements.txt first.")

    client_id = get_env("X_CLIENT_ID", "TWITTER_CLIENT_ID") or payload.get("client_id")
    if not client_id:
        raise RuntimeError("Missing OAuth2 client id.")

    redirect_uri = (
        get_env("X_OAUTH2_REDIRECT_URI", "TWITTER_OAUTH2_REDIRECT_URI")
        or payload.get("redirect_uri")
    )
    if not redirect_uri:
        raise RuntimeError("Missing OAuth2 redirect URI.")

    scopes = payload.get("scopes") if isinstance(payload.get("scopes"), list) else None
    client_secret = get_env("X_CLIENT_SECRET", "TWITTER_CLIENT_SECRET")
    token = payload.get("token") if isinstance(payload.get("token"), dict) else None

    return OAuth2PKCEAuth(
        client_id=client_id,
        client_secret=client_secret or None,
        redirect_uri=redirect_uri,
        token=token,
        scope=scopes,
    )


def muted(text: str) -> str:
    if not sys.stdout.isatty() or "NO_COLOR" in os.environ:
        return text
    return f"{ANSI_GRAY}{text}{ANSI_RESET}"


def print_help():
    print(muted(HELP_TEXT.rstrip()))


def print_usage():
    print_help()


def upgrade_app() -> int:
    if INSTALL_SCRIPT.exists():
        result = subprocess.run(
            ["/usr/bin/env", "bash", str(INSTALL_SCRIPT), "upgrade"],
            check=False,
            text=True,
            env=os.environ.copy(),
        )
        return result.returncode

    with urllib.request.urlopen(INSTALL_SCRIPT_URL) as response:
        script_body = response.read()

    with tempfile.NamedTemporaryFile(delete=False) as handle:
        handle.write(script_body)
        script_path = Path(handle.name)

    try:
        script_path.chmod(0o700)
        result = subprocess.run(
            ["/usr/bin/env", "bash", str(script_path), "upgrade"],
            check=False,
            text=True,
            env=os.environ.copy(),
        )
        return result.returncode
    finally:
        script_path.unlink(missing_ok=True)


def _load_oauth2_token_payload():
    token_file = _oauth2_token_file_path()
    if not os.path.isfile(token_file):
        return token_file, None
    try:
        with open(token_file, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return token_file, None
    return token_file, payload if isinstance(payload, dict) else None


def _save_oauth2_token_payload(token_file, payload):
    token_dir = os.path.dirname(token_file)
    if token_dir:
        os.makedirs(token_dir, exist_ok=True)
    with open(token_file, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _extract_access_token(payload):
    if not isinstance(payload, dict):
        return None

    token_obj = payload.get("token")
    if isinstance(token_obj, dict):
        expires_at = token_obj.get("expires_at")
        if isinstance(expires_at, (int, float)) and int(expires_at) <= int(time.time()):
            return None
        access_token = token_obj.get("access_token")
        if isinstance(access_token, str) and access_token.strip():
            return access_token.strip()

    access_token = payload.get("access_token")
    if isinstance(access_token, str) and access_token.strip():
        return access_token.strip()
    return None


def _refresh_oauth2_access_token(token_file, payload):
    try:
        auth = _build_oauth2_auth(payload)
        refreshed = auth.refresh_token()
    except Exception:
        return None
    if not isinstance(refreshed, dict):
        return None

    token_obj = payload.get("token") if isinstance(payload.get("token"), dict) else {}
    refresh_token = (
        get_env("X_OAUTH2_REFRESH_TOKEN", "TWITTER_OAUTH2_REFRESH_TOKEN")
        or token_obj.get("refresh_token")
        or payload.get("refresh_token")
    )
    if not refreshed.get("refresh_token"):
        refreshed["refresh_token"] = refresh_token

    updated_payload = dict(payload)
    updated_payload["created_at"] = int(time.time())
    updated_payload["token"] = refreshed
    _save_oauth2_token_payload(token_file, updated_payload)
    return _extract_access_token(updated_payload)


def get_user_access_token(auto_refresh=True):
    env_token = (
        get_env("X_USER_ACCESS_TOKEN", "TWITTER_USER_ACCESS_TOKEN")
        or get_env("X_OAUTH2_USER_TOKEN", "TWITTER_OAUTH2_USER_TOKEN")
        or get_env("X_BEARER_TOKEN", "TWITTER_BEARER_TOKEN")
    )
    if env_token:
        return env_token

    token_file, payload = _load_oauth2_token_payload()
    access_token = _extract_access_token(payload)
    if access_token:
        return access_token
    if auto_refresh and isinstance(payload, dict):
        return _refresh_oauth2_access_token(token_file, payload)
    return None


def _run_oauth2_login_helper():
    try:
        from oauth2_login import main as oauth2_login_main
    except ImportError as exc:
        helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), "oauth2_login.py")
        if not os.path.isfile(helper):
            raise RuntimeError(f"Missing helper script: {helper}") from exc
        return subprocess.call([sys.executable, helper])

    try:
        original_argv = list(sys.argv)
        sys.argv = ["oauth2_login.py"]
        oauth2_login_main()
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        print(str(code), file=sys.stderr)
        return 1
    finally:
        sys.argv = original_argv
    return 0


def _validate_oauth2_user_token(oauth2_user_token):
    xdk_client = _build_xdk_client(oauth2_user_token)
    _authenticated_user_id(xdk_client)
    return oauth2_user_token


def _ensure_valid_oauth2_user_token():
    return _validate_oauth2_user_token(_ensure_oauth2_user_token())


def _build_xdk_client(access_token):
    xdk_symbols = _xdk_symbols()
    if xdk_symbols is None:
        raise RuntimeError("Missing dependency: xdk. Install requirements.txt first.")
    if not access_token:
        raise RuntimeError("Missing OAuth2 user access token for XDK client.")
    XdkClient = xdk_symbols[0]
    return XdkClient(access_token=access_token)


def _ensure_oauth2_user_token():
    oauth2_user_token = get_user_access_token(auto_refresh=True)
    if oauth2_user_token:
        return oauth2_user_token
    print(
        "No valid OAuth2 user token found. Starting browser login...",
        file=sys.stderr,
    )
    rc = _run_oauth2_login_helper()
    if rc == 0:
        oauth2_user_token = get_user_access_token(auto_refresh=True)
    if not oauth2_user_token:
        raise SystemExit("OAuth2 token check failed.")
    return oauth2_user_token


def _response_to_dict(payload):
    if isinstance(payload, dict):
        return payload
    if hasattr(payload, "model_dump"):
        return payload.model_dump(exclude_none=True)
    return {}


def _retry_delay_seconds(response, attempt):
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(1, min(int(retry_after), 60))
        except ValueError:
            pass
    return min(2 ** attempt, 16)


def _xdk_call_with_retries(method, *args, retries=MEDIA_UPLOAD_RETRIES, **kwargs):
    requests = _requests_module()
    for attempt in range(retries + 1):
        try:
            return method(*args, **kwargs)
        except requests.HTTPError as exc:
            response = exc.response
            status = response.status_code if response is not None else None
            if status not in RETRYABLE_STATUS_CODES or attempt == retries:
                if response is not None:
                    request_id = response.headers.get("x-request-id")
                    body = (response.text or "").strip()
                    detail = f"X API error {status}"
                    if request_id:
                        detail += f" (x-request-id: {request_id})"
                    if body:
                        detail += f": {body}"
                    raise RuntimeError(detail) from exc
                raise
            time.sleep(_retry_delay_seconds(response, attempt))
        except requests.RequestException:
            if attempt == retries:
                raise
            time.sleep(min(2 ** attempt, 16))

def _payload_data(payload):
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload if isinstance(payload, dict) else {}


def _payload_data_list(payload):
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    return []


def _coerce_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _normalize_bookmarks_page(payload):
    includes = payload.get("includes") or {}
    users = includes.get("users") or []
    user_by_id = {}
    for item in users:
        if isinstance(item, dict) and item.get("id") is not None:
            user_by_id[str(item["id"])] = item

    items = []
    for tweet in _payload_data_list(payload):
        if not isinstance(tweet, dict):
            continue
        tweet_id = _coerce_text(tweet.get("id"))
        if not tweet_id:
            continue
        author = user_by_id.get(_coerce_text(tweet.get("author_id")), {})
        username = _coerce_text(author.get("username"))
        items.append(
            {
                "tweet_id": tweet_id,
                "conversation_id": _coerce_text(tweet.get("conversation_id")) or tweet_id,
                "text": _coerce_text(tweet.get("text")),
                "author_id": _coerce_text(author.get("id")) or _coerce_text(tweet.get("author_id")),
                "author_name": _coerce_text(author.get("name")),
                "author_username": username,
                "created_at": _coerce_text(tweet.get("created_at")),
                "reply_settings": _coerce_text(tweet.get("reply_settings")),
                "url": f"https://x.com/{username or 'i'}/status/{tweet_id}",
            }
        )
    return items


def _authenticated_user_id(xdk_client):
    response = xdk_client.users.get_me(user_fields=["id", "name", "username"])
    payload = _response_to_dict(response)
    user = _payload_data(payload)
    user_id = _coerce_text(user.get("id"))
    if not user_id:
        raise RuntimeError("X API returned no authenticated user id.")
    return user_id


def get_bookmarks(xdk_client, limit=100):
    user_id = _authenticated_user_id(xdk_client)
    bookmarks = []
    remaining = max(1, int(limit))
    per_page = min(remaining, 100)
    pages = xdk_client.users.get_bookmarks(
        user_id,
        max_results=per_page,
        tweet_fields=["author_id", "conversation_id", "created_at", "reply_settings"],
        expansions=["author_id"],
        user_fields=["id", "name", "username"],
    )
    for page in pages:
        payload = _response_to_dict(page)
        bookmarks.extend(_normalize_bookmarks_page(payload))
        if len(bookmarks) >= limit:
            break
    return bookmarks[:limit]


def delete_bookmark(xdk_client, tweet_id):
    user_id = _authenticated_user_id(xdk_client)
    response = xdk_client.users.delete_bookmark(user_id, tweet_id)
    return _response_to_dict(response)


def _media_id_from_payload(payload):
    data = _payload_data(payload)
    media_id = (
        data.get("id")
        or data.get("media_id_string")
        or data.get("media_id")
        or payload.get("media_id_string")
        or payload.get("media_id")
    )
    if not media_id:
        raise RuntimeError("Upload succeeded but media_id was missing in response.")
    return str(media_id)


def _detect_media_type(path):
    media_type, _ = mimetypes.guess_type(path)
    if media_type:
        return media_type

    extension = os.path.splitext(path)[1].lower()
    fallback_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
    }
    media_type = fallback_types.get(extension)
    if media_type:
        return media_type

    raise RuntimeError(
        f"Unsupported media type for '{path}'. Use a common image/video format."
    )


def _media_category_for_type(media_type):
    if media_type == "image/gif":
        return "tweet_gif"
    if media_type.startswith("image/"):
        return "tweet_image"
    if media_type.startswith("video/"):
        return "tweet_video"
    raise RuntimeError(
        f"Unsupported media type '{media_type}'. Only images, GIFs, and videos are supported."
    )


def _wait_for_media_processing(media_client, media_id, processing_info):
    attempts = 0
    if not isinstance(processing_info, dict):
        processing_info = _response_to_dict(processing_info)
    while processing_info:
        state = processing_info.get("state")
        if state == "succeeded":
            return
        if state == "failed":
            error = processing_info.get("error") or {}
            code = error.get("code", "unknown")
            message = error.get("message", "unknown failure")
            raise RuntimeError(f"Media processing failed ({code}): {message}")
        if state not in ("pending", "in_progress"):
            raise RuntimeError(f"Unexpected media processing state: {state}")

        attempts += 1
        if attempts > 30:
            raise RuntimeError("Timed out waiting for media processing.")

        wait_seconds = int(processing_info.get("check_after_secs", 2))
        wait_seconds = max(1, min(wait_seconds, 30))
        time.sleep(wait_seconds)

        status_response = _xdk_call_with_retries(
            media_client.get_upload_status,
            media_id,
            command="STATUS",
            retries=MEDIA_UPLOAD_RETRIES,
        )
        status_payload = _response_to_dict(status_response)
        processing_info = _payload_data(status_payload).get("processing_info")


def _chunked_media_upload(media_client, media_path, media_type, media_category):
    xdk_symbols = _xdk_symbols()
    if xdk_symbols is None:
        raise RuntimeError("Missing dependency: xdk. Install requirements.txt first.")
    AppendUploadRequest = xdk_symbols[1]
    InitializeUploadRequest = xdk_symbols[2]
    total_bytes = os.path.getsize(media_path)
    init_response = _xdk_call_with_retries(
        media_client.initialize_upload,
        InitializeUploadRequest(
            total_bytes=total_bytes,
            media_type=media_type,
            media_category=media_category,
        ),
        retries=MEDIA_UPLOAD_RETRIES,
    )
    init_payload = _response_to_dict(init_response)
    media_id = _media_id_from_payload(init_payload)

    with open(media_path, "rb") as media_file:
        segment_index = 0
        while True:
            chunk = media_file.read(MEDIA_CHUNK_SIZE)
            if not chunk:
                break

            encoded_chunk = base64.b64encode(chunk).decode("ascii")
            _xdk_call_with_retries(
                media_client.append_upload,
                media_id,
                AppendUploadRequest(
                    media=encoded_chunk,
                    segment_index=segment_index,
                ),
                retries=MEDIA_UPLOAD_RETRIES,
            )
            segment_index += 1

    finalize_response = _xdk_call_with_retries(
        media_client.finalize_upload,
        media_id,
        retries=MEDIA_UPLOAD_RETRIES,
    )
    finalize_payload = _response_to_dict(finalize_response)
    processing_info = _payload_data(finalize_payload).get("processing_info")
    _wait_for_media_processing(media_client, media_id, processing_info)
    return media_id


def upload_media(xdk_client, media_path):
    xdk_symbols = _xdk_symbols()
    if xdk_symbols is None:
        raise RuntimeError("Missing dependency: xdk. Install requirements.txt first.")
    UploadRequest = xdk_symbols[3]
    media_path = os.path.expanduser(media_path)
    if not os.path.isfile(media_path):
        raise RuntimeError(f"Media file not found: {media_path}")

    media_type = _detect_media_type(media_path)
    media_category = _media_category_for_type(media_type)
    media_size = os.path.getsize(media_path)
    if media_size <= 0:
        raise RuntimeError(f"Media file is empty: {media_path}")

    media_client = xdk_client.media

    if media_category == "tweet_image" and media_size <= 5 * 1024 * 1024:
        with open(media_path, "rb") as media_file:
            encoded_media = base64.b64encode(media_file.read()).decode("ascii")
        upload_response = _xdk_call_with_retries(
            media_client.upload,
            UploadRequest(
                media=encoded_media,
                media_category=media_category,
                media_type=media_type,
            ),
            retries=MEDIA_UPLOAD_RETRIES,
        )
        payload = _response_to_dict(upload_response)
        media_id = _media_id_from_payload(payload)
        _wait_for_media_processing(media_client, media_id, _payload_data(payload).get("processing_info"))
        return media_id

    return _chunked_media_upload(media_client, media_path, media_type, media_category)


def post_tweet(text, *, xdk_client, media_ids=None, reply_to_tweet_id=None):
    xdk_symbols = _xdk_symbols()
    if xdk_symbols is None:
        raise RuntimeError("Missing dependency: xdk. Install requirements.txt first.")
    CreateRequest = xdk_symbols[4]
    CreateRequestMedia = xdk_symbols[5]
    CreateRequestReply = xdk_symbols[6]
    body = CreateRequest()
    if text:
        body.text = text
    if media_ids:
        body.media = CreateRequestMedia(media_ids=[str(media_id) for media_id in media_ids])
    if reply_to_tweet_id:
        body.reply = CreateRequestReply(
            in_reply_to_tweet_id=str(reply_to_tweet_id),
            auto_populate_reply_metadata=True,
        )
    return _xdk_call_with_retries(
        xdk_client.posts.create,
        body,
        retries=MEDIA_UPLOAD_RETRIES,
    )


def _find_phrase(args, phrase):
    phrase = list(phrase)
    limit = len(args) - len(phrase) + 1
    for index in range(max(0, limit)):
        if args[index : index + len(phrase)] == phrase:
            return index
    return -1


def _parse_bookmark_list_args(args):
    json_output = False
    count = 100
    index = 0
    while index < len(args):
        token = args[index]
        if token == "json":
            json_output = True
            index += 1
            continue
        if token == "limit":
            if index + 1 >= len(args):
                raise SystemExit("valid shape: x bookmarks list [json] [limit <count>]")
            try:
                count = int(args[index + 1])
            except ValueError:
                raise SystemExit("limit must be a number")
            index += 2
            continue
        raise SystemExit("valid shape: x bookmarks list [json] [limit <count>]")
    return json_output, max(1, count)


def read_from_vim(initial_text=""):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        temp_path = tmp.name
        if initial_text:
            tmp.write(initial_text.encode("utf-8"))
            tmp.flush()

    try:
        while True:
            editor = (os.getenv("VISUAL") or os.getenv("EDITOR") or "vim").strip()
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


def _dispatch_auth(args: list[str]) -> int:
    if args == ["check"]:
        try:
            _ensure_valid_oauth2_user_token()
        except Exception as exc:
            raise SystemExit(f"OAuth2 token validation failed: {exc}")
        print("X OAuth2 token is ready.")
        return 0

    if args == ["refresh"]:
        rc = _run_oauth2_login_helper()
        if rc != 0:
            raise SystemExit("OAuth2 token refresh failed.")
        oauth2_user_token = get_user_access_token(auto_refresh=True)
        if not oauth2_user_token:
            raise SystemExit("OAuth2 token check failed after refresh.")
        try:
            _validate_oauth2_user_token(oauth2_user_token)
        except Exception as exc:
            raise SystemExit(f"OAuth2 token validation failed after refresh: {exc}")
        print("X OAuth2 token is ready.")
        return 0

    raise SystemExit("valid shape: x auth check | x auth refresh")


def _dispatch_bookmarks(args: list[str]) -> int:
    if not args:
        raise SystemExit("valid shape: x bookmarks list [json] [limit <count>] | x bookmarks remove <tweet_id>")

    if args[0] == "list":
        json_output, count = _parse_bookmark_list_args(args[1:])
        oauth2_user_token = _ensure_oauth2_user_token()
        xdk_client = _build_xdk_client(oauth2_user_token)
        bookmarks = get_bookmarks(xdk_client, limit=count)
        if json_output:
            print(json.dumps({"bookmarks": bookmarks}, indent=2))
            return 0
        if not bookmarks:
            print("No bookmarks found.")
            return 0
        for index, bookmark in enumerate(bookmarks, start=1):
            header = f"[{index}] {bookmark['tweet_id']} @{bookmark['author_username'] or 'unknown'}"
            if bookmark["created_at"]:
                header += f" {bookmark['created_at']}"
            print(header)
            print(bookmark["url"])
            print(bookmark["text"] or "-")
            print("")
        return 0

    if args[0] == "remove":
        if len(args) != 2:
            raise SystemExit("valid shape: x bookmarks remove <tweet_id>")
        oauth2_user_token = _ensure_oauth2_user_token()
        xdk_client = _build_xdk_client(oauth2_user_token)
        delete_bookmark(xdk_client, args[1])
        print(f"Removed bookmark. id={args[1]}")
        return 0

    raise SystemExit("valid shape: x bookmarks list [json] [limit <count>] | x bookmarks remove <tweet_id>")


def _dispatch_reply(args: list[str]) -> int:
    if len(args) < 4 or args[0] != "to":
        raise SystemExit("valid shape: x reply to <tweet_id> body <text> | x reply to <tweet_id> in editor")

    tweet_id = args[1]
    reply_args = args[2:]
    if reply_args == ["in", "editor"]:
        text = read_from_vim()
    elif reply_args and reply_args[0] == "body":
        text = " ".join(reply_args[1:]).strip()
    else:
        raise SystemExit("valid shape: x reply to <tweet_id> body <text> | x reply to <tweet_id> in editor")

    if not text:
        raise SystemExit("Reply text is required.")
    oauth2_user_token = _ensure_valid_oauth2_user_token()
    xdk_client = _build_xdk_client(oauth2_user_token)
    result = post_tweet(text, xdk_client=xdk_client, reply_to_tweet_id=tweet_id)
    result_payload = _response_to_dict(result)
    posted_tweet_id = result_payload.get("data", {}).get("id", "unknown")
    print(f"Posted reply to X. id={posted_tweet_id}")
    return 0


def _dispatch_post(args: list[str]) -> int:
    if not args:
        print_help()
        return 0
    if any(arg in {"-e", "-m"} for arg in args):
        raise SystemExit("valid shape: x post <text> [with media <path>] | x post in editor [with media <path>]")

    media_path = None
    if args[:2] == ["in", "editor"]:
        rest = args[2:]
        if rest:
            if len(rest) == 3 and rest[:2] == ["with", "media"]:
                media_path = rest[2]
            else:
                raise SystemExit("valid shape: x post in editor [with media <path>]")
        text = read_from_vim()
    else:
        media_index = _find_phrase(args, ["with", "media"])
        if media_index >= 0:
            media_args = args[media_index + 2 :]
            if media_index == 0 or len(media_args) != 1:
                raise SystemExit("valid shape: x post <text> with media <path>")
            text = " ".join(args[:media_index]).strip()
            media_path = media_args[0]
        else:
            text = " ".join(args).strip()

    if not text and not media_path:
        print_help()
        return 0

    oauth2_user_token = _ensure_valid_oauth2_user_token()
    xdk_client = _build_xdk_client(oauth2_user_token)

    media_ids = None
    if media_path:
        media_ids = [upload_media(xdk_client, media_path)]

    result = post_tweet(text, xdk_client=xdk_client, media_ids=media_ids)
    result_payload = _response_to_dict(result)
    tweet_id = result_payload.get("data", {}).get("id", "unknown")
    if media_ids:
        print(f"Posted to X with media. id={tweet_id}")
        return 0
    print(f"Posted to X. id={tweet_id}")
    return 0


def _dispatch(argv: list[str]) -> int:
    command = argv[0]
    command_args = argv[1:]
    if command == "post":
        return _dispatch_post(command_args)
    if command == "auth":
        return _dispatch_auth(command_args)
    if command == "bookmarks":
        return _dispatch_bookmarks(command_args)
    if command == "reply":
        return _dispatch_reply(command_args)
    raise SystemExit(
        "valid commands: x post | x auth check | x auth refresh | x bookmarks list | x bookmarks remove | x reply to"
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print_help()
        return 0
    if args == ["help"]:
        print_help()
        return 0
    if args == ["version"]:
        print(__version__)
        return 0
    if args == ["upgrade"]:
        return upgrade_app()
    if args[0] in {"help", "version", "upgrade"}:
        raise SystemExit("Use x help, x version, or x upgrade by itself.")
    return _dispatch(args)


if __name__ == "__main__":
    raise SystemExit(main())
