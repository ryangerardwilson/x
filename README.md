# x

Minimal CLI to post to X from the command line.

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Set credentials (OAuth 1.0a user context):

```bash
export X_CONSUMER_KEY="..."
export X_CONSUMER_SECRET="..."
export X_ACCESS_TOKEN="..."
export X_ACCESS_TOKEN_SECRET="..."
```

You can also use `TWITTER_*` equivalents for the same values.

For media uploads (`--media` or positional media path), set an OAuth 2.0 user token:

```bash
export X_USER_ACCESS_TOKEN="..."
```

(`X_OAUTH2_USER_TOKEN` is also accepted.)

You can fetch an OAuth2 user token with PKCE login:

```bash
python oauth2_login.py --client-id "$X_CLIENT_ID"
```

If your X app is a confidential client, also set:

```bash
export X_CLIENT_SECRET="..."
```

X Developer Console callback URL for this flow:

```text
https://callback-omega-one.vercel.app/callback/x
```

Set that same value in runtime if needed (optional, already default):

```bash
export X_OAUTH2_REDIRECT_URI="https://callback-omega-one.vercel.app/callback/x"
```

By default this saves token JSON to `~/.x/oauth2_token.json`, which `main.py` reads automatically.
If no valid OAuth2 token is found at post time, `main.py` automatically starts this login flow.

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
