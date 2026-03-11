#!/usr/bin/env python3
import argparse
import json
import os
import secrets
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

DEFAULT_SCOPES = "tweet.read tweet.write users.read media.write bookmark.read bookmark.write offline.access"
DEFAULT_REDIRECT_URI = "https://callback-omega-one.vercel.app/callback/x"


def _default_token_file():
    data_home = os.getenv("XDG_DATA_HOME")
    if data_home:
        base = os.path.expanduser(data_home)
    else:
        base = os.path.expanduser("~/.local/share")
    return os.path.join(base, "x", "tokens", "oauth2_token.json")


def _env(name, fallback=None):
    value = os.getenv(name)
    if value:
        return value
    if fallback:
        return os.getenv(fallback)
    return None

def _oauth2_pkce_auth_class():
    try:
        from xdk.oauth2_auth import OAuth2PKCEAuth
    except ImportError:
        return None
    return OAuth2PKCEAuth


class _CallbackHandler(BaseHTTPRequestHandler):
    data = {"code": None, "state": None, "error": None}
    event = None

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        _CallbackHandler.data["code"] = (query.get("code") or [None])[0]
        _CallbackHandler.data["state"] = (query.get("state") or [None])[0]
        _CallbackHandler.data["error"] = (query.get("error") or [None])[0]

        body = "Authorization complete. You can close this window."
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

        if _CallbackHandler.event:
            _CallbackHandler.event.set()

    def log_message(self, format, *args):  # noqa: A003
        return


def _extract_code_from_callback_input(value):
    raw = (value or "").strip()
    if not raw:
        return None, None, None
    if "://" not in raw:
        return raw, None, None
    parsed = urllib.parse.urlparse(raw)
    query = urllib.parse.parse_qs(parsed.query)
    code = (query.get("code") or [None])[0]
    state = (query.get("state") or [None])[0]
    error = (query.get("error") or [None])[0]
    return code, state, error


def _build_oauth2_auth(*, client_id, client_secret, redirect_uri, scopes, token=None):
    OAuth2PKCEAuth = _oauth2_pkce_auth_class()
    if OAuth2PKCEAuth is None:
        raise RuntimeError("Missing dependency: xdk. Install requirements.txt first.")
    return OAuth2PKCEAuth(
        client_id=client_id,
        client_secret=client_secret or None,
        redirect_uri=redirect_uri,
        token=token,
        scope=scopes,
    )


def _build_callback_url(redirect_uri, code, state):
    params = {"code": code}
    if state:
        params["state"] = state
    return f"{redirect_uri}?{urllib.parse.urlencode(params)}"


def _save_token(token_file, payload):
    token_path = os.path.expanduser(token_file)
    os.makedirs(os.path.dirname(token_path), exist_ok=True)
    with open(token_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return token_path


def main():
    parser = argparse.ArgumentParser(
        description="Authenticate with X OAuth 2.0 PKCE and save a user access token."
    )
    parser.add_argument(
        "--client-id",
        default=_env("X_CLIENT_ID", "CLIENT_ID"),
        help="OAuth2 Client ID (defaults to X_CLIENT_ID/CLIENT_ID).",
    )
    parser.add_argument(
        "--client-secret",
        default=_env("X_CLIENT_SECRET", "CLIENT_SECRET"),
        help="Optional Client Secret for confidential clients.",
    )
    parser.add_argument(
        "--redirect-uri",
        default=_env("X_OAUTH2_REDIRECT_URI", "REDIRECT_URI") or DEFAULT_REDIRECT_URI,
        help="Redirect URI configured in your app settings (defaults to hosted callback service).",
    )
    parser.add_argument(
        "--scopes",
        default=_env("X_OAUTH2_SCOPES") or DEFAULT_SCOPES,
        help="Space-delimited scopes.",
    )
    parser.add_argument(
        "--token-file",
        default=_env("X_OAUTH2_TOKEN_FILE") or _default_token_file(),
        help="Where to store token JSON.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open browser automatically; print URL only.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Seconds to wait for local callback before timing out.",
    )
    args = parser.parse_args()

    if not args.client_id:
        entered_client_id = input("Enter X OAuth2 Client ID: ").strip()
        if not entered_client_id:
            raise SystemExit("Missing Client ID. Set X_CLIENT_ID or pass --client-id.")
        args.client_id = entered_client_id

    state = secrets.token_urlsafe(24)
    auth = _build_oauth2_auth(
        client_id=args.client_id,
        client_secret=args.client_secret,
        redirect_uri=args.redirect_uri,
        scopes=args.scopes.split(),
    )
    authorize_url = auth.get_authorization_url(state=state)

    parsed_redirect = urllib.parse.urlparse(args.redirect_uri)
    use_local_callback = (
        parsed_redirect.scheme == "http"
        and parsed_redirect.hostname in ("127.0.0.1", "localhost")
        and parsed_redirect.port
    )

    code = None
    callback_error = None
    if use_local_callback:
        event = threading.Event()
        _CallbackHandler.event = event
        _CallbackHandler.data = {"code": None, "state": None, "error": None}

        server = HTTPServer((parsed_redirect.hostname, parsed_redirect.port), _CallbackHandler)
        server.timeout = 0.5
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
    else:
        server = None

    try:
        print("Open this URL to authorize the app:")
        print(authorize_url)
        if not args.no_open:
            webbrowser.open(authorize_url)

        if use_local_callback:
            if not event.wait(args.timeout):
                raise SystemExit(
                    "Timed out waiting for OAuth callback. Ensure redirect URI matches app settings."
                )
            callback_error = _CallbackHandler.data.get("error")
            callback_state = _CallbackHandler.data.get("state")
            code = _CallbackHandler.data.get("code")
            if callback_error:
                raise SystemExit(f"Authorization failed: {callback_error}")
            if callback_state != state:
                raise SystemExit("State mismatch in callback; aborting for safety.")
            callback_input = _build_callback_url(args.redirect_uri, code, callback_state)
        else:
            pasted = input(
                "Paste the full callback URL here. If you only have the callback page values, paste the code and you will be prompted for state: "
            ).strip()
            code, callback_state, callback_error = _extract_code_from_callback_input(
                pasted
            )
            if callback_error:
                raise SystemExit(f"Authorization failed: {callback_error}")
            if callback_state and callback_state != state:
                raise SystemExit("State mismatch in callback URL; aborting for safety.")
            if "://" in pasted:
                callback_input = pasted
            else:
                callback_state = input("Paste the callback state: ").strip()
                if not callback_state:
                    raise SystemExit("Callback state is required when pasting only the code.")
                if callback_state != state:
                    raise SystemExit("State mismatch in callback values; aborting for safety.")
                callback_input = pasted

        if not code:
            raise SystemExit("No authorization code received.")

        try:
            if "://" in callback_input:
                token = auth.fetch_token(authorization_response=callback_input)
            else:
                token = auth.exchange_code(callback_input)
        except RuntimeError as exc:
            message = str(exc)
            missing_auth_header = "unauthorized_client" in message and "authorization header" in message.lower()
            if missing_auth_header and not args.client_secret:
                entered_client_secret = input(
                    "X requires a Client Secret for this app. Enter X_CLIENT_SECRET: "
                ).strip()
                if not entered_client_secret:
                    raise
                auth = _build_oauth2_auth(
                    client_id=args.client_id,
                    client_secret=entered_client_secret,
                    redirect_uri=args.redirect_uri,
                    scopes=args.scopes.split(),
                )
                if "://" in callback_input:
                    token = auth.fetch_token(authorization_response=callback_input)
                else:
                    token = auth.exchange_code(callback_input)
            else:
                raise
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()

    payload = {
        "created_at": int(time.time()),
        "client_id": args.client_id,
        "redirect_uri": args.redirect_uri,
        "scopes": args.scopes.split(),
        "token": token,
    }
    token_path = _save_token(args.token_file, payload)

    access_token = token.get("access_token")
    refresh_token = token.get("refresh_token")
    print("")
    print(f"Saved OAuth2 token to: {token_path}")
    if access_token:
        print("Export for current shell:")
        print(f'export X_USER_ACCESS_TOKEN="{access_token}"')
    if refresh_token:
        print(f'export X_OAUTH2_REFRESH_TOKEN="{refresh_token}"')


if __name__ == "__main__":
    main()
