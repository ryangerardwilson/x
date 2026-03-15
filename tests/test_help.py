import os
import subprocess
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch


APP = Path(__file__).resolve().parents[1] / "main.py"
APP_DIR = APP.parent
VERSION_PATH = APP_DIR / "_version.py"
CONTRACT_SRC = APP.parents[1] / "rgw_cli_contract" / "src"

sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(CONTRACT_SRC))


def load_version():
    namespace = {}
    exec(VERSION_PATH.read_text(encoding="utf-8"), namespace)
    return namespace["__version__"]


class HelpOutputTests(unittest.TestCase):
    def test_no_arg_matches_help(self):
        env = os.environ.copy()
        existing = env.get("PYTHONPATH")
        parts = [str(CONTRACT_SRC)]
        if existing:
            parts.append(existing)
        env["PYTHONPATH"] = os.pathsep.join(parts)
        no_arg = subprocess.run(
            [sys.executable, str(APP)],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        help_arg = subprocess.run(
            [sys.executable, str(APP), "-h"],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        self.assertEqual(no_arg.stdout, help_arg.stdout)

    def test_help_uses_flags_and_features_layout(self):
        env = os.environ.copy()
        existing = env.get("PYTHONPATH")
        parts = [str(CONTRACT_SRC)]
        if existing:
            parts.append(existing)
        env["PYTHONPATH"] = os.pathsep.join(parts)
        result = subprocess.run(
            [sys.executable, str(APP), "-h"],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )

        self.assertIn("flags:\n", result.stdout)
        self.assertIn("features:\n", result.stdout)
        self.assertIn("# x p <text>", result.stdout)
        self.assertIn("# x ea [-r]", result.stdout)
        self.assertIn("x ea -r", result.stdout)
        self.assertIn("# x b ls [-j] [-n <count>]", result.stdout)
        self.assertIn("# x r <tweet_id> <text> | x r <tweet_id> -e", result.stdout)
        self.assertIn("x p -m ~/media/demo.mp4 -e", result.stdout)

    def test_version_prints_single_value(self):
        env = os.environ.copy()
        existing = env.get("PYTHONPATH")
        parts = [str(CONTRACT_SRC)]
        if existing:
            parts.append(existing)
        env["PYTHONPATH"] = os.pathsep.join(parts)
        result = subprocess.run(
            [sys.executable, str(APP), "-v"],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        self.assertEqual(result.stdout.strip(), load_version())

    def test_upgrade_passes_u_to_installer(self):
        from main import APP_SPEC, _dispatch, main

        with patch("main.run_app", return_value=0) as run_app:
            rc = main(["-u"])

        self.assertEqual(rc, 0)
        self.assertEqual(run_app.call_args.args[0], APP_SPEC)
        self.assertEqual(run_app.call_args.args[1], ["-u"])
        self.assertIs(run_app.call_args.args[2], _dispatch)


if __name__ == "__main__":
    unittest.main()
