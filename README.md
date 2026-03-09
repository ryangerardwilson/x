# x

Minimal terminal CLI for publishing to X.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/ryangerardwilson/x/main/install.sh | bash
```

## Setup

Set your X OAuth2 app credentials for PKCE login:

```bash
export X_CLIENT_ID="..."
```

If your app is a confidential client, also set:

```bash
export X_CLIENT_SECRET="..."
```

Callback URL:

```text
https://callback-omega-one.vercel.app/callback/x
```

Optional redirect override:

```bash
export X_OAUTH2_REDIRECT_URI="https://callback-omega-one.vercel.app/callback/x"
```

Manual token bootstrap:

```bash
python oauth2_login.py --client-id "$X_CLIENT_ID"
```

Default token path:

```text
~/.local/share/x/tokens/oauth2_token.json
```

Token env override:

```bash
export X_USER_ACCESS_TOKEN="..."
```

Also accepted: `X_OAUTH2_USER_TOKEN`, `X_BEARER_TOKEN`.

Optional text-only fallback: `X_CONSUMER_KEY`, `X_CONSUMER_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`, or `TWITTER_*`.

## Usage

```text
x CLI

flags:
  x -h
  x -v
  x -u

features:
  publish text directly
  # x p <text>
  x p "ship the patch"

  publish with media using the canonical media flag
  # x p <text> -m <path>
  x p "ship the patch" -m ~/media/demo.mp4

  compose in the editor
  # x p -e | x p -m <path> -e
  x p -e
  x p -m ~/media/demo.mp4 -e

  validate OAuth2 auth and exit
  # x ea
  x ea
```

If the draft exceeds 280 characters, the CLI prompts for re-edit or cancel.

## Auth Behavior

- OAuth2 user token is preferred for posting.
- `-m` requires an OAuth2 user token with media scope.
- Text-only publish can fall back to OAuth1 credentials if OAuth2 is unavailable.

## Source Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py -h
```

## Release workflow

Tags like `v0.1.0` trigger GitHub Actions to build `x-linux-x64.tar.gz` and publish a release.
