"""Start an isolated loopback backend and web server, then record a new demo."""

import contextlib
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests


def run():
    out = Path("recordings") / time.strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True)
    # Email/password are transient when emulators:exec starts a clean instance.
    env = dict(
        os.environ,
        TEXTILE_PROJECT="demo-textilesense",
        TEXTILE_TOKEN=secrets.token_hex(32),
    )
    env.setdefault("DEMO_PASSWORD", secrets.token_urlsafe(24))
    if not Path("mobile/dist/index.html").exists():
        raise SystemExit("Run scripts/setup.sh first to export the Expo application")
    subprocess.run([sys.executable, "provision.py"], env=env, check=True)
    with contextlib.ExitStack() as stack:
        for kind in ("api", "web"):
            sock = stack.enter_context(socket.socket())
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            url = f"http://127.0.0.1:{port}"
            log = stack.enter_context((out / (kind + ".log")).open("w"))
            if kind == "api":
                env["TEXTILE_API_URL"] = url
                cmd = ["-m", "uvicorn", "api:app", "--fd", str(sock.fileno())]
                pass_fds = (sock.fileno(),)
                check = url + "/openapi.json"
            else:
                sock.close()
                env["TEXTILE_WEB_URL"] = url
                cmd = [
                    "-m",
                    "http.server",
                    str(port),
                    "--bind",
                    "127.0.0.1",
                    "--directory",
                    "mobile/dist",
                ]
                pass_fds = ()
                check = url
            proc = subprocess.Popen(
                [sys.executable, *cmd],
                pass_fds=pass_fds,
                env=env,
                stdout=log,
                stderr=log,
            )

            def stop(p=proc):
                if p.poll() is None:
                    p.terminate()
                    p.wait(timeout=15)

            stack.callback(stop)
            for _ in range(100):
                if proc.poll() is not None:
                    raise RuntimeError(f"{kind} exited; see {log.name}")
                try:
                    if requests.get(check, timeout=0.5).ok:
                        break
                except requests.ConnectionError:
                    pass
                time.sleep(0.2)
            else:
                raise RuntimeError(f"{kind} readiness timed out")
        subprocess.run(
            [sys.executable, "-m", "proof.record_demo", "--output", str(out)],
            check=True,
            env=env,
        )
    print("Saved", out / "demonstration.mp4")


if __name__ == "__main__":
    run()
