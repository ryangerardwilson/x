import os
import subprocess
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch


APP = Path(__file__).resolve().parents[1] / "main.py"
APP_DIR = APP.parent
VERSION_PATH = APP_DIR / "_version.py"

sys.path.insert(0, str(APP_DIR))


def load_version():
    namespace = {}
    exec(VERSION_PATH.read_text(encoding="utf-8"), namespace)
    return namespace["__version__"]


class HelpOutputTests(unittest.TestCase):
    def test_no_arg_matches_help(self):
        env = os.environ.copy()
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
        result = subprocess.run(
            [sys.executable, str(APP), "-h"],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )

        self.assertIn("flags:\n", result.stdout)
        self.assertIn("features:\n", result.stdout)
        self.assertIn("# x post <text>", result.stdout)
        self.assertIn("# x auth check | x auth refresh", result.stdout)
        self.assertIn("x auth refresh", result.stdout)
        self.assertIn("# x bookmarks list [json] [limit <count>]", result.stdout)
        self.assertIn("# x reply to <tweet_id> body <text> | x reply to <tweet_id> in editor", result.stdout)
        self.assertIn("x post in editor with media ~/media/demo.mp4", result.stdout)
        self.assertNotIn("x p ", result.stdout)
        self.assertNotIn("x ea", result.stdout)

    def test_version_prints_single_value(self):
        env = os.environ.copy()
        result = subprocess.run(
            [sys.executable, str(APP), "-v"],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        self.assertEqual(result.stdout.strip(), load_version())

    def test_upgrade_passes_u_to_installer(self):
        from main import INSTALL_SCRIPT, main

        with patch("main.subprocess.run") as subprocess_run:
            subprocess_run.return_value.returncode = 0
            rc = main(["-u"])

        self.assertEqual(rc, 0)
        self.assertEqual(
            subprocess_run.call_args.args[0],
            ["/usr/bin/env", "bash", str(INSTALL_SCRIPT), "-u"],
        )


if __name__ == "__main__":
    unittest.main()
