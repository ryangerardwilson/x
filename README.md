# x

Terminal CLI for publishing to X and handling bookmark-driven reply flows.

`x version` prints the installed app version from `_version.py`. Source checkouts keep a placeholder value; tagged release builds stamp the shipped artifact with the real version.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/ryangerardwilson/x/main/install.sh | bash
```

If `~/.local/bin` is not already on your `PATH`, add it once to `~/.bashrc`
and reload your shell:

```bash
export PATH="$HOME/.local/bin:$PATH"
source ~/.bashrc
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

For bookmark-driven reply flows, the token needs:

```text
tweet.read tweet.write users.read media.write bookmark.read bookmark.write offline.access
```

## Usage

```text
x CLI

global actions:
  x help
  x version
  x upgrade

features:
  publish text directly
  # x post <text>
  x post "ship the patch"

  publish with media
  # x post <text> with media <path>
  x post "ship the patch" with media ~/media/demo.mp4

  compose in the editor
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
```

If the draft exceeds 280 characters, the CLI prompts for re-edit or cancel.

## Version And Upgrade

```bash
x version
x upgrade
```

`x upgrade` delegates installation work to the top-level `install.sh` contract.

## Auth Behavior

- OAuth2 user token is required for posting.
- `x auth refresh` forces a fresh OAuth2 login and rewrites the saved token.
- Bookmark lookup and removal require an OAuth2 user token with bookmark scopes.
- Media posts require an OAuth2 user token with media scope.
- X API calls use the X SDK path; there is no raw HTTP publish fallback.

## Source Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py help
```

## Release workflow

Tag the desired `v<version>` release and let the release workflow stamp `_version.py` in the shipped bundle before publishing `x-linux-x64.tar.gz`.
