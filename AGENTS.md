# x Agent Guide

## Workspace Defaults
- Follow `/home/ryan/Subagents/cpo/CLI_TUI_STYLE_GUIDE.md` for CLI/TUI taste and help shape.
- Follow `/home/ryan/Subagents/cto/CANONICAL_REFERENCE_IMPLEMENTATION_FOR_CLI_AND_TUI_APPS.md` for executable contract details such as `help`, `version`, `upgrade`, installer behavior, release workflow expectations, and regression expectations.
- This file only records `x`-specific constraints or durable deviations.

## Scope
- `x` is a terminal CLI for publishing to X and handling the minimal bookmark/reply flows that support `replyguy`.
- Keep the interface keyboard-first and explicit. Do not turn this repo into a generic social scheduler or GUI wrapper.
- Supported primary flows are: text post, media post, editor compose, auth check, bookmark list/remove, reply post, version, and self-upgrade.

## CLI Contract
- Only `help`, `version`, and `upgrade` remain as global launcher actions.
- `x` with no content should print the same help text as `x help`.
- Help output must include concrete examples and must not document GNU-style long flags for the app itself.
- Canonical command grammar is declarative English only:
  - `x post "text"`
  - `x post "text" with media /path/to/file`
  - `x post in editor`
  - `x post in editor with media /path/to/file`
  - `x auth check`
  - `x auth refresh`
  - `x bookmarks list [json] [limit <count>]`
  - `x bookmarks remove <tweet_id>`
  - `x reply to <tweet_id> body "text"`
  - `x reply to <tweet_id> in editor`
- Do not keep terse aliases such as `p`, `ea`, `b ls`, `b rm`, `r`, `-e`, or `-m`.
- Success output should stay terse and include the posted id.

## Auth And Storage
- Default OAuth2 token storage must use XDG data paths, currently `~/.local/share/x/tokens/oauth2_token.json` unless `XDG_DATA_HOME` or explicit env overrides are set.
- Keep environment overrides working for operators.
- Do not reintroduce default token storage under `~/.x/`.
- Observed behavior: a token generated successfully while running `python main.py` may not work after upgrading and running the installed `x` binary. In that case, re-run auth under the installed `x` binary and mint a fresh token there.
- X API calls should go through the X SDK only. Do not add or reintroduce raw HTTP publish flows as a fallback.
- When changing OAuth2 or SDK usage, study the official X SDK Python samples first: `https://github.com/xdevplatform/samples/tree/main/python`. Load the smallest relevant sample set for the flow you are touching instead of inventing the auth or client pattern from scratch.

## Editing And UX
- Editor resolution order is `$VISUAL`, then `$EDITOR`, then `vim`.
- Error messages should reference declarative commands and the three global launcher actions only.
- Keep output plain-text and deterministic.

## Repo Guardrails
- `_version.py` is the single runtime version module.
- Keep the checked-in value as a placeholder and let tagged release automation stamp the shipped artifact with the real version.
- `install.sh` must expose word actions (`help`, `version`, `upgrade`, `from`) rather than dash meta flags, and user-facing app hints must stay on the same declarative grammar.
- Keep runtime logic small and local unless complexity clearly justifies another module.
