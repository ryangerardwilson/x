import sys
import types
import unittest
import importlib.util
from io import StringIO
from pathlib import Path
from unittest.mock import patch


APP = Path(__file__).resolve().parents[1] / "main.py"
sys.path.insert(0, str(APP.parent))
SPEC = importlib.util.spec_from_file_location("x_main", APP)
assert SPEC and SPEC.loader
main = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(main)


class AuthFlowTests(unittest.TestCase):
    def test_auth_check_validates_token_with_live_path(self):
        with patch.object(sys, "argv", ["main.py", "ea"]):
            with patch.object(main, "_ensure_valid_oauth2_user_token", side_effect=RuntimeError("boom")):
                with self.assertRaises(SystemExit) as exc:
                    main.main()
        self.assertEqual(str(exc.exception), "OAuth2 token validation failed: boom")

    def test_auth_reissue_validates_reissued_token(self):
        with patch.object(sys, "argv", ["main.py", "ea", "-r"]):
            with patch.object(main, "_run_oauth2_login_helper", return_value=0):
                with patch.object(main, "get_user_access_token", return_value="token"):
                    with patch.object(main, "_validate_oauth2_user_token") as validate:
                        with patch("sys.stdout", new=StringIO()) as stdout:
                            main.main()
        validate.assert_called_once_with("token")
        self.assertEqual(stdout.getvalue(), "X OAuth2 token is ready.\n")

    def test_login_helper_runs_in_process_when_module_is_available(self):
        module = types.SimpleNamespace(main=lambda: None)
        with patch.dict(sys.modules, {"oauth2_login": module}):
            with patch("main.subprocess.call") as subprocess_call:
                rc = main._run_oauth2_login_helper()
        self.assertEqual(rc, 0)
        subprocess_call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
