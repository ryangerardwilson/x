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

## Usage

Post directly:

```bash
python main.py "hello, world"
```

Compose in Vim:

```bash
python main.py -e
```

If the draft exceeds 280 characters, you'll be prompted to re-edit or cancel.

## CLI Flags

- `-e`, `--edit`: Open Vim to compose a post.
- `-v`, `--version`: Print version and exit.
- `-u`, `--upgrade`: Upgrade via the installer script.
- `-h`, `--help`: Show help.

## Install (binary release)

```bash
curl -fsSL https://raw.githubusercontent.com/ryangerardwilson/x/main/install.sh | bash
```

## Release workflow

Tags like `v0.1.0` trigger GitHub Actions to build `x-linux-x64.tar.gz` and publish a release.
