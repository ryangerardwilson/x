# x Agent Guide

## Scope
- `x` is a single-purpose terminal CLI for publishing to X.
- Keep the interface keyboard-first and explicit. Do not turn this repo into a generic social scheduler or GUI wrapper.
- Supported primary flows are: text post, media post, editor compose, auth check, version, and self-upgrade.

## CLI Contract
- Canonical app flags are short only: `-h`, `-v`, `-u`, `-e`, `-m`, `-ea`.
- `x` with no content should print the same help text as `x -h`.
- Help output must include concrete examples and must not document GNU-style long flags for the app itself.
- Preserve the current publish grammar:
  - `x "text"`
  - `x -m /path/to/file "text"`
  - `x "text" /path/to/file`
- Success output should stay terse and include the posted id.

## Auth And Storage
- Default OAuth2 token storage must use XDG data paths, currently `~/.local/share/x/tokens/oauth2_token.json` unless `XDG_DATA_HOME` or explicit env overrides are set.
- Keep environment overrides working for operators.
- Do not reintroduce default token storage under `~/.x/`.
- Text-only fallback via OAuth1 env vars is supported and should remain explicit in help/docs.

## Editing And UX
- Editor resolution order is `$VISUAL`, then `$EDITOR`, then `vim`.
- Error messages should reference only canonical short flags.
- Keep output plain-text and deterministic.

## Repo Guardrails
- `_version.py` remains the single source of runtime version.
- `install.sh` may keep conventional long installer flags, but user-facing app hints should reference the canonical app flags.
- Keep runtime logic small and local unless complexity clearly justifies another module.
