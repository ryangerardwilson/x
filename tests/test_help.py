import subprocess
import sys
from pathlib import Path
import unittest


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


if __name__ == "__main__":
    unittest.main()
