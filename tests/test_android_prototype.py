"""The Android scheduler runs protocol work on LDN's Trio thread and closes its worker."""
import subprocess
import sys
from pathlib import Path


def test_android_shared_loop_thread_ownership_and_close_grace():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root / 'examples/android/check_shared_loop.py')],
                            cwd=root, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
