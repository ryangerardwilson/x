# x

Minimal CLI to post to X from the command line.

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Set your X OAuth2 app credentials (for PKCE login):

```bash
export X_CLIENT_ID="..."
```

If your X app is a confidential client, also set:

```bash
export X_CLIENT_SECRET="..."
```

X Developer Console callback URL for this flow:

```text
https://callback-omega-one.vercel.app/callback/x
```

Set the same redirect URI in runtime if needed (optional; this is already the default in `oauth2_login.py`):

```bash
export X_OAUTH2_REDIRECT_URI="https://callback-omega-one.vercel.app/callback/x"
```

You can fetch an OAuth2 user token manually:

```bash
python oauth2_login.py --client-id "$X_CLIENT_ID"
```

Or let `main.py` do it automatically: when no valid token is found, it launches `oauth2_login.py`.
By default tokens are saved to:

```text
~/.x/oauth2_token.json
```

You can also provide a token directly instead of login:

```bash
export X_USER_ACCESS_TOKEN="..."
```

`X_OAUTH2_USER_TOKEN` and `X_BEARER_TOKEN` are also accepted.

Optional fallback for text-only posts: set OAuth 1.0a user credentials (`X_CONSUMER_KEY`, `X_CONSUMER_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`), or `TWITTER_*` equivalents.

Notes:
- The CLI now uses the official Python XDK for v2 media upload and post creation.
- Access tier matters. `POST /2/tweets` and media upload may fail until your app has an eligible paid tier (for example, pay-as-you-go).

## Usage

Post directly:

```bash
python main.py "hello, world"
```

Post with media:

```bash
python main.py "hello, world" /path/to/image-or-video
```

or:

```bash
python main.py "hello, world" --media /path/to/image-or-video
```

Compose in Vim:

```bash
python main.py -e
```

If the draft exceeds 280 characters, you'll be prompted to re-edit or cancel.

## Auth Behavior

- OAuth2 user token is preferred for posting.
- With `--media`, OAuth2 user token is required (`media.write` scope).
- For text-only posts, if OAuth2 is unavailable, the CLI can fall back to OAuth1 credentials.

## CLI Flags

- `-e`, `--edit`: Open Vim to compose a post.
- `-m`, `--media`: Attach an image, GIF, or video from a local file path.
- `-v`, `--version`: Print version and exit.
- `-u`, `--upgrade`: Upgrade via the installer script.
- `-h`, `--help`: Show help.

## Install (binary release)

```bash
curl -fsSL https://raw.githubusercontent.com/ryangerardwilson/x/main/install.sh | bash
```

## Release workflow

Tags like `v0.1.0` trigger GitHub Actions to build `x-linux-x64.tar.gz` and publish a release.
