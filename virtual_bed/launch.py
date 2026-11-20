"""Provision a local viewer and start the simulator, API and Expo web dashboard."""

import os
import secrets
import subprocess
import sys
import time

import requests

from store import database


def provision_local(db):
    password = os.getenv("DEMO_PASSWORD") or secrets.token_urlsafe(10)
    email = "viewer@example.test"
    base = "http://127.0.0.1:9199/identitytoolkit.googleapis.com/v1/accounts:"
    body = dict(email=email, password=password, returnSecureToken=True)
    auth = requests.post(base + "signUp?key=demo", json=body, timeout=5)
    if not auth.ok and auth.json().get("error", {}).get("message") == "EMAIL_EXISTS":
        auth = requests.post(base + "signInWithPassword?key=demo", json=body, timeout=5)
    auth.raise_for_status()
    db.document("devices/virtual-mat-01").set(
        dict(source="virtual_pressure_mat", rows=32, cols=64, units="simulated counts")
    )
    db.document("sessions/virtual-bed").set(
        dict(device="virtual-mat-01", readers=[auth.json()["localId"]])
    )
    return f"Dashboard viewer: {email}\nLocal demo password: {password}"


def main():
    db = database()
    if os.environ["TEXTILE_PROJECT"] == "demo-textilesense-bed":
        message = provision_local(db)
    else:
        session = db.document("sessions/virtual-bed").get().to_dict() or {}
        if session.get("device") != "virtual-mat-01" or not session.get("readers"):
            raise RuntimeError(
                "Provision the session and a viewer in Firestore first. See VIRTUAL_BED.md."
            )
        message = "Sign in with the approved hosted viewer account."
    env = dict(
        os.environ,
        TEXTILE_TOKEN=secrets.token_hex(32),
        TEXTILE_API_URL="http://127.0.0.1:18735",
    )
    servers = []
    try:
        for module, port in (("api:app", 18735), ("virtual_bed.controller:app", 8775)):
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    module,
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--no-access-log",
                ],
                env=env,
            )
            servers.append(proc)
            for _ in range(100):
                if proc.poll() is not None:
                    raise RuntimeError(f"Could not launch {module} on port {port}")
                try:
                    if requests.get(
                        f"http://127.0.0.1:{port}/openapi.json", timeout=0.5
                    ).ok:
                        break
                except requests.ConnectionError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError(f"{module} readiness timed out")
        print(
            f"Open http://127.0.0.1:8775\n{message}\nCtrl+C ends the demo.", flush=True
        )
        while all(p.poll() is None for p in servers):
            time.sleep(0.5)
        raise RuntimeError("A demo service exited")
    finally:
        for p in reversed(servers):
            p.terminate()
            p.wait()


if __name__ == "__main__":
    main()
