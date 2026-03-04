# Repository Guidelines

## Project Structure & Module Organization
- `main.py`: primary CLI entrypoint (`argparse`), tweet posting logic, editor flow, and self-upgrade behavior.
- `_version.py`: single source for runtime version string.
- `requirements.txt`: pinned runtime Python dependencies.
- `install.sh`: Linux installer used by end users and upgrade path.
- `.github/workflows/release.yml`: tag-driven release pipeline; builds `x-linux-x64.tar.gz`.
- `.github/scripts/find-python-url.py`: helper script used during release image build.

Keep new runtime logic in small functions in `main.py` unless complexity justifies splitting into modules.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate`: create and activate a local environment.
- `pip install -r requirements.txt`: install runtime dependencies.
- `python main.py --help`: verify CLI argument parsing and flags.
- `python main.py --version`: check local version wiring.
- `python main.py "hello"`: manual post flow test (requires `X_*` env vars).
- `bash install.sh --help`: validate installer options.

Release builds are handled by GitHub Actions on tags matching `v*` (for example, `v0.1.0`).

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation and clear function names (`snake_case`).
- Prefer small, single-purpose functions and explicit error messages.
- Constants should be uppercase (`INSTALL_URL`, `LATEST_RELEASE_API`).
- Shell scripts should use `set -euo pipefail` and long, descriptive variable names.

## Testing Guidelines
- No automated test suite is currently configured.
- For code changes, run targeted manual checks:
  - CLI parse/help/version paths.
  - `-e` editor flow and 280-character guard behavior.
  - Failure messages for missing credentials.
- If adding tests, use `pytest` under `tests/` with names like `test_<feature>.py`.

## Commit & Pull Request Guidelines
- Current history uses short messages like `sync`; prefer clearer imperative subjects going forward (example: `fix upgrade version comparison`).
- Keep commits focused and logically grouped.
- PRs should include:
  - What changed and why.
  - How it was validated (commands run).
  - Related issue links, if any.
  - CLI output snippets for behavior changes.

## Security & Configuration Tips
- Never commit `X_CONSUMER_KEY`, `X_CONSUMER_SECRET`, `X_ACCESS_TOKEN`, or `X_ACCESS_TOKEN_SECRET`.
- Use environment variables locally; avoid hardcoded secrets in code or scripts.
