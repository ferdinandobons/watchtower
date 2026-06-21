from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run(module_args: list[str], env: dict[str, str], timeout: float = 10) -> None:
    subprocess.run(
        [sys.executable, "-m", "watchtower", *module_args],
        check=True,
        env=env,
        timeout=timeout,
    )


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(prefix="watchtower-smoke-") as directory:
        root = Path(directory)
        env = os.environ.copy()
        source = str(repository / "src")
        env["PYTHONPATH"] = os.pathsep.join(
            value for value in (source, env.get("PYTHONPATH")) if value
        )
        env["WATCHTOWER_DB_PATH"] = str(root / "watchtower.db")
        env["WATCHTOWER_CHECKPOINTS_DIR"] = str(root / "checkpoints")
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "watchtower",
                "serve",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-notifications",
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            for _ in range(50):
                if process.poll() is not None:
                    output = process.stdout.read() if process.stdout else ""
                    raise RuntimeError(f"Watchtower daemon exited before readiness:\n{output}")
                try:
                    with urllib.request.urlopen(f"{url}/health", timeout=0.2) as response:
                        if response.status == 200:
                            break
                except (OSError, urllib.error.URLError, TimeoutError):
                    time.sleep(0.1)
            else:
                raise RuntimeError("Watchtower daemon did not become ready")

            _run(["demo", "--url", url], env)
            _run(["doctor", "--url", url], env)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
