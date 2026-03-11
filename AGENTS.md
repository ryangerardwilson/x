# x Agent Guide

## Workspace Defaults
- Follow `/home/ryan/Documents/agent_context/CLI_TUI_STYLE_GUIDE.md` for CLI/TUI taste and help shape.
- Follow `/home/ryan/Documents/agent_context/CANONICAL_REFERENCE_IMPLEMENTATION_FOR_CLI_AND_TUI_APPS.md` for executable contract details such as `-h`, `-v`, `-u`, installer behavior, release workflow expectations, and regression expectations.
- This file only records `x`-specific constraints or durable deviations.

## Scope
- `x` is a terminal CLI for publishing to X and handling the minimal bookmark/reply flows that support `replyguy`.
- Keep the interface keyboard-first and explicit. Do not turn this repo into a generic social scheduler or GUI wrapper.
- Supported primary flows are: text post, media post, editor compose, auth check, bookmark list/remove, reply post, version, and self-upgrade.

## CLI Contract
- Canonical app flags are short only: `-h`, `-v`, `-u`, `-e`, `-m`.
- `x` with no content should print the same help text as `x -h`.
- Help output must include concrete examples and must not document GNU-style long flags for the app itself.
- Preserve the current publish grammar:
  - `x p "text"`
  - `x p "text" -m /path/to/file`
  - `x p -e`
  - `x p -m /path/to/file -e`
- Auth check grammar is `x ea`.
- Success output should stay terse and include the posted id.

## Auth And Storage
- Default OAuth2 token storage must use XDG data paths, currently `~/.local/share/x/tokens/oauth2_token.json` unless `XDG_DATA_HOME` or explicit env overrides are set.
- Keep environment overrides working for operators.
- Do not reintroduce default token storage under `~/.x/`.
- X API calls should go through the X SDK only. Do not add or reintroduce raw HTTP publish flows as a fallback.
- When changing OAuth2 or SDK usage, study the official X SDK Python samples first: `https://github.com/xdevplatform/samples/tree/main/python`. Load the smallest relevant sample set for the flow you are touching instead of inventing the auth or client pattern from scratch.

## Editing And UX
- Editor resolution order is `$VISUAL`, then `$EDITOR`, then `vim`.
- Error messages should reference only canonical short flags.
- Keep output plain-text and deterministic.

## Repo Guardrails
- `_version.py` is the single runtime version module.
- Keep the checked-in value as a placeholder and let tagged release automation stamp the shipped artifact with the real version.
- `install.sh` may keep conventional long installer flags, but user-facing app hints should reference the canonical app flags.
- Keep runtime logic small and local unless complexity clearly justifies another module.
