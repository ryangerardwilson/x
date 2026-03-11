import argparse
import base64
import json
import mimetypes
import os
import shlex
import subprocess
import sys
import tempfile
import time

try:
    from _version import __version__
except Exception:
    __version__ = "0.0.0"

INSTALL_URL = "https://raw.githubusercontent.com/ryangerardwilson/x/main/install.sh"
LATEST_RELEASE_API = "https://api.github.com/repos/ryangerardwilson/x/releases/latest"
X_OAUTH2_TOKEN_URL = "https://api.x.com/2/oauth2/token"
MEDIA_CHUNK_SIZE = 4 * 1024 * 1024
MEDIA_UPLOAD_RETRIES = 8
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
ANSI_RESET = "\033[0m"
ANSI_GRAY = "\033[38;5;245m"


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


def _muted_text(text):
    if not sys.stdout.isatty() or "NO_COLOR" in os.environ:
        return text
    return f"{ANSI_GRAY}{text}{ANSI_RESET}"


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


def _oauth1_class():
    try:
        from requests_oauthlib import OAuth1
    except ImportError:
        return None
    return OAuth1


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


def _urllib_parse():
    import urllib.parse

    return urllib.parse


def _urllib_request_symbols():
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen

    return Request, urlopen, HTTPError, URLError


def build_auth():
    OAuth1 = _oauth1_class()
    if OAuth1 is None:
        raise RuntimeError("Missing dependency: requests-oauthlib. Install requirements.txt first.")
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


def _oauth2_token_file_path():
    token_file = (
        get_env("X_OAUTH2_TOKEN_FILE", "TWITTER_OAUTH2_TOKEN_FILE")
        or _default_oauth2_token_file()
    )
    return os.path.expanduser(token_file)


def print_usage():
    print(
        _muted_text(
        "X CLI\n"
        "publish to X and manage reply workflows from the terminal\n"
        "\n"
        "flags:\n"
        "  x -h\n"
        "    show this help\n"
        "  x -v\n"
        "    print the installed version\n"
        "  x -u\n"
        "    upgrade to the latest release\n"
        "\n"
        "features:\n"
        "  publish text directly\n"
        "  # x p <text>\n"
        "  x p \"ship the patch\"\n"
        "\n"
        "  publish with media using the canonical media flag\n"
        "  # x p <text> -m <path>\n"
        "  x p \"ship the patch\" -m ~/media/demo.mp4\n"
        "\n"
        "  compose in the editor resolved from $VISUAL, then $EDITOR, then vim\n"
        "  # x p -e | x p -m <path> -e\n"
        "  x p -e\n"
        "  x p -m ~/media/demo.mp4 -e\n"
        "\n"
        "  validate OAuth2 auth and exit, or force token re-issuance\n"
        "  # x ea [-r]\n"
        "  x ea\n"
        "  x ea -r\n"
        "\n"
        "  list bookmarked posts for reply workflows\n"
        "  # x b ls [-j] [-n <count>]\n"
        "  x b ls\n"
        "  x b ls -j -n 20\n"
        "\n"
        "  remove a bookmark after you have handled it\n"
        "  # x b rm <tweet_id>\n"
        "  x b rm 1894451234567890123\n"
        "\n"
        "  post a reply to a bookmarked post\n"
        "  # x r <tweet_id> <text> | x r <tweet_id> -e\n"
        "  x r 1894451234567890123 \"The useful test is whether it survives contact with ops.\"\n"
        "  x r 1894451234567890123 -e\n"
        )
    )


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
    urllib_parse = _urllib_parse()
    Request, urlopen, HTTPError, URLError = _urllib_request_symbols()
    token_obj = payload.get("token") if isinstance(payload.get("token"), dict) else {}
    refresh_token = (
        get_env("X_OAUTH2_REFRESH_TOKEN", "TWITTER_OAUTH2_REFRESH_TOKEN")
        or token_obj.get("refresh_token")
        or payload.get("refresh_token")
    )
    if not refresh_token:
        return None

    client_id = get_env("X_CLIENT_ID", "TWITTER_CLIENT_ID") or payload.get("client_id")
    if not client_id:
        return None
    client_secret = get_env("X_CLIENT_SECRET", "TWITTER_CLIENT_SECRET")

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if client_secret:
        basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode(
            "utf-8"
        )
        headers["Authorization"] = f"Basic {basic}"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }

    encoded = urllib_parse.urlencode(data).encode("utf-8")
    request = Request(X_OAUTH2_TOKEN_URL, data=encoded, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read()
            status_code = response.getcode()
            response_headers = response.headers
    except (HTTPError, URLError, TimeoutError, OSError):
        return None
    response = _HttpResponse(status_code, response_headers, body)
    if response.status_code < 200 or response.status_code >= 300:
        return None

    try:
        refreshed = response.json()
    except ValueError:
        return None
    if not isinstance(refreshed, dict):
        return None

    expires_in = int(refreshed.get("expires_in") or 0)
    if expires_in > 0:
        refreshed["expires_at"] = int(time.time()) + expires_in
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
    helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), "oauth2_login.py")
    if not os.path.isfile(helper):
        raise RuntimeError(f"Missing helper script: {helper}")
    return subprocess.call([sys.executable, helper])


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


def _raise_for_x_error(response):
    if 200 <= response.status_code < 300:
        return
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        errors = payload.get("errors")
        if isinstance(errors, list):
            for err in errors:
                if isinstance(err, dict) and err.get("code") == 453:
                    raise RuntimeError(
                        "X API access error (453): this app/token is restricted to a subset of endpoints. "
                        "Your current access level does not allow the attempted endpoint. "
                        "Check your plan in https://developer.x.com/en/portal/product, then regenerate user tokens."
                    )
    if response.status_code == 503:
        raise RuntimeError(
            "X API error 503: Media service unavailable after retries. "
            "This is typically transient on X's side; retry in 30-120 seconds."
        )
    raise RuntimeError(f"X API error {response.status_code}: {response.text.strip()}")


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


def _urllib_request(method, url, headers=None, json_body=None, form_body=None, timeout=30):
    urllib_parse = _urllib_parse()
    Request, urlopen, HTTPError, _ = _urllib_request_symbols()
    request_headers = dict(headers or {})
    body = None
    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    elif form_body is not None:
        body = urllib_parse.urlencode(form_body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")

    request = Request(url, data=body, headers=request_headers, method=method.upper())
    try:
        with urlopen(request, timeout=timeout) as response:
            return _HttpResponse(response.getcode(), response.headers, response.read())
    except HTTPError as exc:
        return _HttpResponse(exc.code, exc.headers, exc.read())


def _request_with_retries(method, url, auth=None, headers=None, retries=4, **kwargs):
    if auth is None:
        _, _, _, URLError = _urllib_request_symbols()
        timeout = kwargs.get("timeout", 30)
        json_body = kwargs.get("json")
        form_body = kwargs.get("data")
        for attempt in range(retries + 1):
            try:
                response = _urllib_request(
                    method,
                    url,
                    headers=headers,
                    json_body=json_body,
                    form_body=form_body,
                    timeout=timeout,
                )
            except (URLError, TimeoutError, OSError):
                if attempt == retries:
                    raise
                time.sleep(min(2 ** attempt, 16))
                continue
            if response.status_code not in RETRYABLE_STATUS_CODES:
                return response
            if attempt == retries:
                return response
            time.sleep(_retry_delay_seconds(response, attempt))
        return response

    requests = _requests_module()
    for attempt in range(retries + 1):
        response = requests.request(method, url, auth=auth, headers=headers, **kwargs)
        if response.status_code not in RETRYABLE_STATUS_CODES:
            return response
        if attempt == retries:
            return response
        time.sleep(_retry_delay_seconds(response, attempt))
    return response


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
        tweet_fields=["author_id", "conversation_id", "created_at"],
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


def post_tweet(auth, headers, text, media_ids=None, xdk_client=None, reply_to_tweet_id=None):
    if xdk_client is not None:
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

    payload = {}
    if text:
        payload["text"] = text
    if media_ids:
        payload["media"] = {"media_ids": [str(media_id) for media_id in media_ids]}
    if reply_to_tweet_id:
        payload["reply"] = {
            "in_reply_to_tweet_id": str(reply_to_tweet_id),
            "auto_populate_reply_metadata": True,
        }

    response = _request_with_retries(
        "POST",
        "https://api.x.com/2/tweets",
        auth=auth,
        headers=headers,
        json=payload,
        timeout=30,
    )
    if 200 <= response.status_code < 300:
        return response.json()

    _raise_for_x_error(response)
    return response.json()


def build_top_level_parser():
    parser = argparse.ArgumentParser(
        description="Post to X from the command line.",
        add_help=False,
    )
    parser.add_argument("-h", dest="help_flag", action="store_true", help="Show help and exit.")
    parser.add_argument("-v", dest="version", action="store_true", help="Show version and exit.")
    parser.add_argument("-u", dest="upgrade", action="store_true", help="Upgrade to the latest version.")
    parser.add_argument("command", nargs="?", help="Command: p, ea, b, or r.")
    parser.add_argument("command_args", nargs=argparse.REMAINDER)
    return parser


def build_publish_parser():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-h", dest="help_flag", action="store_true", help="Show help and exit.")
    parser.add_argument("-m", dest="media", help="Path to an image/GIF/video to attach.")
    parser.add_argument("-e", dest="edit", action="store_true", help="Open Vim to compose the post.")
    parser.add_argument("text", nargs="*", help="Post text. If omitted, use -e to open Vim.")
    return parser


def build_bookmark_parser():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-h", dest="help_flag", action="store_true", help="Show help and exit.")
    parser.add_argument("bookmark_command", nargs="?", help="Bookmark command: ls or rm.")
    parser.add_argument("bookmark_args", nargs=argparse.REMAINDER)
    return parser


def build_bookmark_list_parser():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-h", dest="help_flag", action="store_true", help="Show help and exit.")
    parser.add_argument("-j", dest="json_output", action="store_true", help="Print JSON.")
    parser.add_argument("-n", dest="count", type=int, default=100, help="Maximum bookmarks to list.")
    return parser


def build_reply_parser():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-h", dest="help_flag", action="store_true", help="Show help and exit.")
    parser.add_argument("-e", dest="edit", action="store_true", help="Open editor for reply text.")
    parser.add_argument("tweet_id", nargs="?", help="Tweet id to reply to.")
    parser.add_argument("text", nargs=argparse.REMAINDER, help="Reply text.")
    return parser


def build_auth_check_parser():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-h", dest="help_flag", action="store_true", help="Show help and exit.")
    parser.add_argument("-r", dest="reissue", action="store_true", help="Force token re-issuance.")
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
    Request, urlopen, HTTPError, URLError = _urllib_request_symbols()
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


def main():
    parser = build_top_level_parser()
    args = parser.parse_args()

    if args.help_flag:
        print_usage()
        return

    if args.version:
        print(__version__)
        return

    if args.upgrade:
        if args.command or args.command_args:
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

    if not args.command:
        print_usage()
        return

    if args.command == "ea":
        auth_check_parser = build_auth_check_parser()
        auth_args = auth_check_parser.parse_args(args.command_args)
        if auth_args.help_flag:
            print_usage()
            return
        if auth_args.reissue:
            rc = _run_oauth2_login_helper()
            if rc != 0:
                raise SystemExit("OAuth2 token re-issuance failed.")
            if not get_user_access_token(auto_refresh=True):
                raise SystemExit("OAuth2 token check failed after re-issuance.")
        else:
            _ensure_oauth2_user_token()
        print("X OAuth2 token is ready.")
        return

    if args.command == "b":
        bookmark_parser = build_bookmark_parser()
        bookmark_args = bookmark_parser.parse_args(args.command_args)
        if bookmark_args.help_flag or not bookmark_args.bookmark_command:
            print_usage()
            return
        if bookmark_args.bookmark_command == "ls":
            list_parser = build_bookmark_list_parser()
            list_args = list_parser.parse_args(bookmark_args.bookmark_args)
            if list_args.help_flag:
                print_usage()
                return
            oauth2_user_token = _ensure_oauth2_user_token()
            xdk_client = _build_xdk_client(oauth2_user_token)
            bookmarks = get_bookmarks(xdk_client, limit=max(1, list_args.count))
            if list_args.json_output:
                print(json.dumps({"bookmarks": bookmarks}, indent=2))
                return
            if not bookmarks:
                print("No bookmarks found.")
                return
            for index, bookmark in enumerate(bookmarks, start=1):
                header = f"[{index}] {bookmark['tweet_id']} @{bookmark['author_username'] or 'unknown'}"
                if bookmark["created_at"]:
                    header += f" {bookmark['created_at']}"
                print(header)
                print(bookmark["url"])
                print(bookmark["text"] or "-")
                print("")
            return
        if bookmark_args.bookmark_command == "rm":
            if len(bookmark_args.bookmark_args) != 1:
                raise SystemExit("Usage: x b rm <tweet_id>")
            oauth2_user_token = _ensure_oauth2_user_token()
            xdk_client = _build_xdk_client(oauth2_user_token)
            delete_bookmark(xdk_client, bookmark_args.bookmark_args[0])
            print(f"Removed bookmark. id={bookmark_args.bookmark_args[0]}")
            return
        raise SystemExit("Usage: x b ls [-j] [-n <count>] | x b rm <tweet_id>")

    if args.command == "r":
        reply_parser = build_reply_parser()
        reply_args = reply_parser.parse_args(args.command_args)
        if reply_args.help_flag or not reply_args.tweet_id:
            print_usage()
            return
        if reply_args.edit and reply_args.text:
            raise SystemExit("Use `x r <tweet_id> -e` without inline text.")
        if reply_args.edit:
            text = read_from_vim()
        else:
            text = " ".join(reply_args.text).strip()
        if not text:
            raise SystemExit("Reply text is required.")
        oauth2_user_token = _ensure_oauth2_user_token()
        xdk_client = _build_xdk_client(oauth2_user_token)
        result = post_tweet(
            None,
            {"Authorization": f"Bearer {oauth2_user_token}"},
            text,
            xdk_client=xdk_client,
            reply_to_tweet_id=reply_args.tweet_id,
        )
        result_payload = _response_to_dict(result)
        tweet_id = result_payload.get("data", {}).get("id", "unknown")
        print(f"Posted reply to X. id={tweet_id}")
        return

    if args.command != "p":
        raise SystemExit(
            "Usage: x p <text> [-m <path>] | x p -e [-m <path>] | x ea | x b ls [-j] [-n <count>] | x b rm <tweet_id> | x r <tweet_id> <text>"
        )

    publish_parser = build_publish_parser()
    parse_publish = getattr(publish_parser, "parse_intermixed_args", publish_parser.parse_args)
    publish_args = parse_publish(args.command_args)

    if publish_args.help_flag:
        print_usage()
        return

    if publish_args.edit:
        text_parts = list(publish_args.text)
        media_path = publish_args.media
        if text_parts:
            raise SystemExit("Use `x p -e` without inline text.")
        text = read_from_vim()
    else:
        text_parts = list(publish_args.text)
        media_path = publish_args.media
        text = " ".join(text_parts).strip()

    if not text and not media_path:
        print_usage()
        return

    oauth2_user_token = get_user_access_token(auto_refresh=True)
    if not oauth2_user_token:
        try:
            oauth2_user_token = _ensure_oauth2_user_token()
        except SystemExit:
            oauth2_user_token = None

    auth = None
    headers = None
    xdk_client = None
    if oauth2_user_token:
        headers = {"Authorization": f"Bearer {oauth2_user_token}"}
        if media_path:
            xdk_client = _build_xdk_client(oauth2_user_token)
    elif media_path:
        raise SystemExit(
            "Media posting requires a valid OAuth 2.0 user access token with media.write."
        )
    else:
        auth = build_auth()

    media_ids = None
    if media_path:
        media_ids = [upload_media(xdk_client, media_path)]

    result = post_tweet(auth, headers, text, media_ids=media_ids, xdk_client=xdk_client)
    result_payload = _response_to_dict(result)
    tweet_id = result_payload.get("data", {}).get("id", "unknown")
    if media_ids:
        print(f"Posted to X with media. id={tweet_id}")
    else:
        print(f"Posted to X. id={tweet_id}")


if __name__ == "__main__":
    main()
