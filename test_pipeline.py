"""Integration tests require the running loopback API and Firestore emulator."""

import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests

from dataset import recording
from replay import frame
from store import database

if os.getenv("TEXTILE_PROJECT", "demo-textilesense") != "demo-textilesense":
    raise RuntimeError("This test writes only to the local demo emulator")


@pytest.fixture(scope="module")
def session():
    sid = "qa-" + uuid.uuid4().hex[:12]
    ref = database().document("sessions/" + sid)
    ref.set({"device": "mat01", "readers": []})
    yield sid, ref
    for group in ("state", "events"):
        for doc in ref.collection(group).stream():
            doc.reference.delete()
    ref.delete()


def send(f, token=None):
    return requests.post(
        os.getenv("TEXTILE_API_URL", "http://127.0.0.1:8000") + "/frames",
        timeout=10,
        json=f,
        headers={"Authorization": "Bearer " + (token or os.environ["TEXTILE_TOKEN"])},
    )


def test_integrity(session):
    sid, ref = session
    f = frame(recording(12, 2)[34], 0, 12, 2, 34, sid)
    assert send(f, "incorrect").status_code == 401
    for update in (
        {"rows": 31},
        {"values": [1]},
        {"source": "physical"},
        {"session": "../bad"},
        {"values": [-1] * 2048},
        {"captured_ms": int(time.time() * 1000) + 60000},
    ):
        assert send(dict(f, **update)).status_code == 422
    assert send(dict(f, device="other")).status_code == 403
    with ThreadPoolExecutor(2) as pool:
        statuses = [r.json()["status"] for r in pool.map(send, [f, f])]
    assert sorted(statuses) == ["accepted", "duplicates"]
    assert send(dict(f, row=99)).status_code == 409
    latest = ref.collection("state").document("latest").get().to_dict()
    assert latest["count"] == 1 and latest["duplicates"] == 1 and latest["row"] == 34
