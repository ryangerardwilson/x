# x

Terminal CLI for publishing to X and handling bookmark-driven reply flows.

`x -v` prints the installed app version from `_version.py`. Source checkouts keep a placeholder value; tagged release builds stamp the shipped artifact with the real version.

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

For bookmark-driven reply flows, the token needs:

```text
tweet.read tweet.write users.read media.write bookmark.read bookmark.write offline.access
```

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

  validate OAuth2 auth and exit, or force token re-issuance
  # x ea [-r]
  x ea
  x ea -r

  list bookmarked posts for reply workflows
  # x b ls [-j] [-n <count>]
  x b ls
  x b ls -j -n 20

  remove a bookmark after you have handled it
  # x b rm <tweet_id>
  x b rm 1894451234567890123

  post a reply to a bookmarked post
  # x r <tweet_id> <text> | x r <tweet_id> -e
  x r 1894451234567890123 "The useful test is whether it survives contact with ops."
  x r 1894451234567890123 -e
```

If the draft exceeds 280 characters, the CLI prompts for re-edit or cancel.

## Version And Upgrade

```bash
x -v
x -u
```

`x -u` delegates installation work to the top-level `install.sh` contract.

## Auth Behavior

- OAuth2 user token is preferred for posting.
- `x ea -r` forces a fresh OAuth2 login and rewrites the saved token.
- Bookmark lookup and removal require an OAuth2 user token with bookmark scopes.
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

Tag the desired `v<version>` release and let the release workflow stamp `_version.py` in the shipped bundle before publishing `x-linux-x64.tar.gz`.
