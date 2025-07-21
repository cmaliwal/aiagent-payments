import os
import subprocess
import sys
import tempfile

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("CI", "1"), reason="Skipping CLI test unless in CI or explicitly enabled.")


def run_cli(args):
    cmd = [sys.executable, os.path.join("cli", "main.py")] + args
    return subprocess.run(cmd, capture_output=True, text=True)


def test_cli_help():
    result = run_cli(["--help"])
    assert result.returncode == 0
    assert "usage:" in result.stdout


def test_cli_setup_and_plans(tmp_path):
    # Setup
    result = run_cli(["--storage", "file", "--storage-path", str(tmp_path), "setup"])
    assert result.returncode == 0
    # Plans
    result = run_cli(["--storage", "file", "--storage-path", str(tmp_path), "plans"])
    assert result.returncode == 0
    assert "Available payment plans:" in result.stdout


@pytest.mark.skipif(not os.environ.get("CI", "1"), reason="Skipping CLI test unless in CI or explicitly enabled.")
def test_cli_subscribe_and_status():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup
        result = run_cli(["--storage", "file", "--storage-path", tmpdir, "--payment-provider", "mock", "setup"])
        assert result.returncode == 0, f"Setup failed: {result.stdout}\n{result.stderr}"
        # Subscribe
        result = run_cli(
            ["--storage", "file", "--storage-path", tmpdir, "--payment-provider", "mock", "subscribe", "testuser", "pro"]
        )
        assert result.returncode == 0, f"Subscribe failed: {result.stdout}\n{result.stderr}"
        # Status
        result = run_cli(["--storage", "file", "--storage-path", tmpdir, "--payment-provider", "mock", "status", "testuser"])
        assert result.returncode == 0, f"Status failed: {result.stdout}\n{result.stderr}"
        assert "Status for user testuser:" in result.stdout
