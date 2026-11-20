"""Local-only viewer provisioning. Password is supplied via the environment."""

import os

import requests

from store import database

if os.getenv("TEXTILE_PROJECT", "demo-textilesense") != "demo-textilesense":
    raise SystemExit("This fixture is for the emulator")
base = "http://127.0.0.1:9099/identitytoolkit.googleapis.com/v1/accounts:"
body = {
    "email": "viewer@example.test",
    "password": os.environ["DEMO_PASSWORD"],
    "returnSecureToken": True,
}
resp = requests.post(base + "signUp?key=demo", json=body, timeout=5)
if not resp.ok and resp.json()["error"]["message"] == "EMAIL_EXISTS":
    resp = requests.post(base + "signInWithPassword?key=demo", json=body, timeout=5)
resp.raise_for_status()
db = database()
db.document("devices/mat01").set(
    {"source": "PmatData Experiment I", "rows": 32, "cols": 64}
)
db.document("sessions/demo").set(
    {"readers": [resp.json()["localId"]], "device": "mat01"}, merge=True
)
print("Local viewer authorized for demo")
