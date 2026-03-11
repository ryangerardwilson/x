import os
import subprocess
import tempfile
from pathlib import Path
import unittest


INSTALLER = Path(__file__).resolve().parents[1] / "install.sh"


class InstallScriptTests(unittest.TestCase):
    def _write_executable(self, path: Path, body: str) -> None:
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)

    def test_v_without_argument_prints_latest_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bin_dir = tmp_path / "bin"
            home_dir = tmp_path / "home"
            bin_dir.mkdir()
            home_dir.mkdir()

            self._write_executable(
                bin_dir / "curl",
                "#!/usr/bin/bash\n"
                "printf '%s\n' '{\"tag_name\":\"v0.1.21\"}'\n",
            )

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            env["HOME"] = str(home_dir)

            result = subprocess.run(
                ["/usr/bin/bash", str(INSTALLER), "-v"],
                capture_output=True,
                text=True,
                env=env,
                check=True,
            )

            self.assertEqual(result.stdout.strip(), "0.1.21")

    def test_upgrade_same_version_uses_x_v_and_exits_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bin_dir = tmp_path / "bin"
            home_dir = tmp_path / "home"
            bin_dir.mkdir()
            home_dir.mkdir()

            self._write_executable(
                bin_dir / "curl",
                "#!/usr/bin/bash\n"
                "if [[ \"$1\" == \"-fsSL\" && \"$2\" == \"https://api.github.com/repos/ryangerardwilson/x/releases/latest\" ]]; then\n"
                "  printf '%s\n' '{\"tag_name\":\"v0.1.21\"}'\n"
                "  exit 0\n"
                "fi\n"
                "echo unexpected curl call >&2\n"
                "exit 1\n",
            )
            self._write_executable(
                bin_dir / "x",
                "#!/usr/bin/bash\n"
                "if [[ \"$1\" == \"-v\" ]]; then\n"
                "  printf '0.1.21\\n'\n"
                "  exit 0\n"
                "fi\n"
                "echo unexpected x invocation >&2\n"
                "exit 1\n",
            )

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            env["HOME"] = str(home_dir)

            result = subprocess.run(
                ["/usr/bin/bash", str(INSTALLER), "-u"],
                capture_output=True,
                text=True,
                env=env,
                check=True,
            )

            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
