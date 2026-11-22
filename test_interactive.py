"""Interactive frames through the real API and the Firestore emulator.

Start the virtual-bed emulator first (scripts/virtual-bed.cmd or
`firebase emulators:start --config firebase.virtual.json --project demo-textilesense-bed`).
"""

import os
import secrets
import time
import uuid

import pytest

os.environ.setdefault("TEXTILE_PROJECT", "demo-textilesense-bed")
os.environ.setdefault("TEXTILE_EMULATOR_PORT", "8180")
os.environ.setdefault("TEXTILE_TOKEN", secrets.token_hex(32))
if not os.environ["TEXTILE_PROJECT"].startswith("demo-"):
    raise RuntimeError("This test writes only to a local demo emulator")

from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402
from virtual_bed.body import Person  # noqa: E402
from virtual_bed.sensor import MAT_W, MatPlacement, VirtualMat  # noqa: E402

client = TestClient(api.app)
AUTH = {"Authorization": "Bearer " + os.environ["TEXTILE_TOKEN"]}
MAT = MatPlacement()


@pytest.fixture(scope="module")
def session():
    sid = "qa-" + uuid.uuid4().hex[:10]
    ref = api.db.document("sessions/" + sid)
    ref.set({"device": "virtual-mat-01", "readers": []})
    yield sid, ref
    for group in ("state", "events"):
        for d in ref.collection(group).stream():
            d.reference.delete()
    ref.delete()


def frame(sid, seq, person, posture="back"):
    grid, truth = VirtualMat(seed=seq).read(person, MAT)
    return dict(
        schema_version=2,
        source="interactive_virtual_mat",
        device="virtual-mat-01",
        session=sid,
        seq=seq,
        captured_ms=time.time_ns() // 1000000,
        rows=32,
        cols=64,
        unit="mmHg",
        value_scale=0.1,
        values=grid.ravel().tolist(),
        mat=dict(x_m=MAT.x, y_m=MAT.y, pitch_x_m=0.024, pitch_y_m=0.029, bed_w_m=1.52, bed_l_m=2.03),
        simulator=dict(
            person_on_bed=person is not None,
            posture_selected=posture if person else None,
            roll=person.roll if person else 0.0,
            x_m=person.x if person else None,
            y_m=person.y if person else None,
            theta_deg=person.theta if person else None,
            coverage=truth["coverage"],
            body_force_n=truth["body_force_n"],
            mat_force_n=truth["mat_force_n"],
        ),
    )


def latest(ref):
    return ref.collection("state").document("latest").get().to_dict()


def test_schema_is_enforced(session):
    sid, _ = session
    good = frame(sid, 0, Person(x=MAT.x + MAT_W / 2, y=MAT.y + 0.89))
    assert client.post("/frames", json=good, headers={"Authorization": "Bearer wrong"}).status_code == 401
    for bad in (
        {"unit": "kPa"},
        {"value_scale": 1},
        {"values": [5000] * 2048},
        {"values": [1] * 2047},
        {"extra": 1},
        {"simulator": dict(good["simulator"], posture_selected="sitting")},
        {"mat": dict(good["mat"], pitch_x_m=0.03)},
    ):
        assert client.post("/frames", json=dict(good, **bad), headers=AUTH).status_code == 422, bad


def test_prediction_ignores_the_operator_setting(session):
    sid, ref = session
    person = Person(x=MAT.x + MAT_W / 2, y=MAT.y + 0.89, roll=1.0)
    a = frame(sid, 1, person, posture="right")
    b = dict(a, seq=2, simulator=dict(a["simulator"], posture_selected="left", roll=-1.0))
    assert client.post("/frames", json=a, headers=AUTH).json()["status"] == "accepted"
    first = latest(ref)
    assert client.post("/frames", json=b, headers=AUTH).json()["status"] == "accepted"
    second = latest(ref)
    assert first["scores"] == second["scores"]
    assert first["prediction"] == second["prediction"] == "Right"
    assert second["simulator"]["posture_selected"] == "left"  # stored, not used
    assert second["validation"]["sequence"] == "next"
    assert second["model_status"] == "ran"
    assert second["measurement"]["load_kg"] == pytest.approx(75, rel=0.05)
    assert second["model_input"]["grid"].startswith("complete 32 x 64")


def test_empty_mat_is_stored_without_inference(session):
    sid, ref = session
    r = client.post("/frames", json=frame(sid, 3, None), headers=AUTH)
    assert r.json()["status"] == "accepted"
    doc = latest(ref)
    assert doc["prediction"] is None and doc["scores"] == []
    assert doc["model_status"] == "not_run_no_load"
    assert max(doc["values"]) == 0


def test_a_gap_is_reported(session):
    sid, ref = session
    person = Person(x=MAT.x + MAT_W / 2, y=MAT.y + 0.89)
    before = latest(ref)["missing"]
    assert client.post("/frames", json=frame(sid, 7, person), headers=AUTH).json()["status"] == "accepted"
    doc = latest(ref)
    assert doc["validation"]["sequence"] == "gap of 3"
    assert doc["gap_frames"] == 3 and doc["missing"] == before + 3


def test_edge_contact_is_flagged(session):
    sid, ref = session
    person = Person(x=MAT.x + MAT_W, y=MAT.y + 0.89)  # half the body off the mat
    client.post("/frames", json=frame(sid, 8, person), headers=AUTH)
    assert "load_at_mat_edge" in latest(ref)["input_flags"]


def test_unseen_recording_is_scored_but_label_is_not_used(session):
    from dataset import recording

    sid, ref = session
    grid = recording(12, 2)[40].astype(int)
    base = dict(
        schema_version=1, source="recorded_replay", device="virtual-mat-01", session=sid,
        captured_ms=time.time_ns() // 1000000, rows=32, cols=64, values=grid.ravel().tolist(),
        recording="S12-2", row=40,
    )
    assert client.post("/frames", json=dict(base, seq=20, recorded_label="Right"), headers=AUTH).status_code == 200
    first = latest(ref)
    assert client.post("/frames", json=dict(base, seq=21, recorded_label="Left"), headers=AUTH).status_code == 200
    second = latest(ref)
    assert first["scores"] == second["scores"] and first["prediction"] == "Right"
    assert second["recorded_label"] == "Left"  # stored as given, never used
    assert second["measurement"]["contact_cells"] > 300
    assert second["validation"]["unit"].startswith("raw recorded counts")
    bad = dict(base, seq=22, recorded_label="Sitting")
    assert client.post("/frames", json=bad, headers=AUTH).status_code == 422


def test_phone_control_requests_are_rule_checked(session):
    import requests

    sid, ref = session
    auth = "http://127.0.0.1:9199/identitytoolkit.googleapis.com/v1/accounts:signUp?key=demo"

    def viewer():
        body = dict(email=f"v{uuid.uuid4().hex[:8]}@example.test", password="pw-" + uuid.uuid4().hex, returnSecureToken=True)
        r = requests.post(auth, json=body, timeout=5).json()
        return r["localId"], r["idToken"]

    uid, token = viewer()
    stranger, stranger_token = viewer()
    ref.update({"readers": [uid]})
    base = "http://127.0.0.1:8180/v1/projects/demo-textilesense-bed/databases/(default)/documents"

    def commit(as_token, doc_uid, fields, stamp=True):
        write = {"update": {"name": f"projects/demo-textilesense-bed/databases/(default)/documents/sessions/{sid}/controls/{doc_uid}",
                            "fields": fields}}
        if stamp:
            write["updateTransforms"] = [{"fieldPath": "requested_at", "setToServerValue": "REQUEST_TIME"}]
        return requests.post(base + ":commit", json={"writes": [write]},
                             headers={"Authorization": "Bearer " + as_token}, timeout=5).status_code

    def fields(action="source", mode="recordings", subject=12, posture="right"):
        f = {"action": {"stringValue": action}, "device": {"stringValue": "test phone"}}
        f["mode"] = {"stringValue": mode} if mode else {"nullValue": None}
        f["subject"] = {"integerValue": str(subject)} if subject else {"nullValue": None}
        f["posture"] = {"stringValue": posture} if posture else {"nullValue": None}
        return f

    assert commit(token, uid, fields()) == 200
    assert commit(token, uid, fields("start", None, None, None)) == 200
    assert commit(token, uid, fields(action="delete_everything")) == 403
    assert commit(token, uid, fields(subject=5)) == 403
    assert commit(token, uid, fields(), stamp=False) == 403  # must carry server time
    assert commit(token, stranger, fields()) == 403  # someone else's document
    assert commit(stranger_token, stranger, fields()) == 403  # not a session reader
