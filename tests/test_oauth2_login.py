import sys
import types
import unittest
import importlib.util
from io import StringIO
from pathlib import Path
from unittest.mock import patch


APP = Path(__file__).resolve().parents[1] / "oauth2_login.py"
sys.path.insert(0, str(APP.parent))
SPEC = importlib.util.spec_from_file_location("x_oauth2_login", APP)
assert SPEC and SPEC.loader
oauth2_login = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(oauth2_login)


class _FakeAuth:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.fetch_token_calls = []
        self.exchange_code_calls = []

    def get_authorization_url(self, state):
        self.state = state
        return "https://x.example/auth"

    def fetch_token(self, authorization_response):
        self.fetch_token_calls.append(authorization_response)
        return {"access_token": "a", "refresh_token": "r"}

    def exchange_code(self, code):
        self.exchange_code_calls.append(code)
        return {"access_token": "a", "refresh_token": "r"}


class OAuthLoginTests(unittest.TestCase):
    def test_hosted_callback_url_uses_fetch_token(self):
        fake_auth = _FakeAuth()
        fake_module = types.SimpleNamespace(OAuth2PKCEAuth=lambda **kwargs: fake_auth)
        with patch.dict(sys.modules, {"xdk.oauth2_auth": fake_module}):
            with patch.object(
                sys,
                "argv",
                ["oauth2_login.py", "--no-open", "--client-id", "cid", "--client-secret", "sec"],
            ):
                with patch("builtins.input", return_value="https://callback-omega-one.vercel.app/callback/x?code=abc&state=state-1"):
                    with patch("secrets.token_urlsafe", return_value="state-1"):
                        with patch("sys.stdout", new=StringIO()):
                            oauth2_login.main()
        self.assertEqual(fake_auth.fetch_token_calls, ["https://callback-omega-one.vercel.app/callback/x?code=abc&state=state-1"])
        self.assertEqual(fake_auth.exchange_code_calls, [])

    def test_hosted_callback_code_and_state_use_exchange_code(self):
        fake_auth = _FakeAuth()
        fake_module = types.SimpleNamespace(OAuth2PKCEAuth=lambda **kwargs: fake_auth)
        with patch.dict(sys.modules, {"xdk.oauth2_auth": fake_module}):
            with patch.object(
                sys,
                "argv",
                ["oauth2_login.py", "--no-open", "--client-id", "cid", "--client-secret", "sec"],
            ):
                with patch("builtins.input", side_effect=["abc", "state-1"]):
                    with patch("secrets.token_urlsafe", return_value="state-1"):
                        with patch("sys.stdout", new=StringIO()):
                            oauth2_login.main()
        self.assertEqual(fake_auth.fetch_token_calls, [])
        self.assertEqual(fake_auth.exchange_code_calls, ["abc"])


if __name__ == "__main__":
    unittest.main()
