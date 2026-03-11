import subprocess
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch


APP = Path(__file__).resolve().parents[1] / "main.py"


class HelpOutputTests(unittest.TestCase):
    def test_no_arg_matches_help(self):
        no_arg = subprocess.run(
            [sys.executable, str(APP)],
            capture_output=True,
            text=True,
            check=True,
        )
        help_arg = subprocess.run(
            [sys.executable, str(APP), "-h"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(no_arg.stdout, help_arg.stdout)

    def test_help_uses_flags_and_features_layout(self):
        result = subprocess.run(
            [sys.executable, str(APP), "-h"],
            capture_output=True,
            text=True,
            check=True,
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
        result = subprocess.run(
            [sys.executable, str(APP), "-v"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(result.stdout.strip(), "0.0.0")

    def test_upgrade_passes_u_to_installer(self):
        from main import _run_upgrade

        curl_process = MagicMock()
        curl_process.stdout = MagicMock()
        curl_process.wait.return_value = 0
        curl_process.stderr = MagicMock()
        bash_process = MagicMock()
        bash_process.wait.return_value = 0

        with patch("main.subprocess.Popen", side_effect=[curl_process, bash_process]) as popen:
            rc = _run_upgrade()

        self.assertEqual(rc, 0)
        self.assertEqual(popen.call_args_list[1].args[0], ["bash", "-s", "--", "-u"])


if __name__ == "__main__":
    unittest.main()
