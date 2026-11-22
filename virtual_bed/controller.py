"""Loopback-only operator console for the interactive virtual bed.

The browser moves the mat and the person. This process owns the scene, turns
it into mat readings, and sends one complete frame per second through the
normal authenticated ingestion API, which validates it, runs the CNN and
commits it to Firestore. The console then reads the committed document back
and listens for render receipts from signed-in phones.
"""

import asyncio
import copy
import math
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import numpy as np
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from dataset import recording
from store import database
from virtual_bed.body import LEFT_T, RIGHT_T, SUPINE_T, Person
from virtual_bed.sensor import (
    BED_L,
    BED_W,
    MAT_L,
    MAT_W,
    PX,
    PY,
    MatPlacement,
    VirtualMat,
    bed_field,
    clamp_person,
    measure,
)

SESSION = os.getenv("TEXTILE_SESSION", "virtual-bed")
DEVICE = "virtual-mat-01"
STATIC = Path(__file__).with_name("static")
DIST = Path(os.getenv("VIRTUAL_WEB_DIST", ".cache/virtual-web"))
RATE_HZ = 1.0
ROLL_SECONDS = 1.4
local_demo = os.environ.get("TEXTILE_PROJECT", "").startswith("demo-")
CAP = int(os.getenv("TEXTILE_FRAME_CAP", "1800" if local_demo else "900"))
API_URL = os.getenv("TEXTILE_API_URL", "http://127.0.0.1:8000")

db = database()
session_ref = db.document(f"sessions/{SESSION}")
latest_ref = session_ref.collection("state").document("latest")
lock = threading.RLock()
sensor = VirtualMat()


class Scene:
    def __init__(self):
        self.mat: MatPlacement | None = None
        self.person: Person | None = None
        self.posture = "back"
        self.version = 0

    def snapshot(self):
        with lock:
            return copy.deepcopy(self.mat), copy.deepcopy(self.person), self.posture


scene = Scene()
TARGET = {"back": 0.0, "left": -1.0, "right": 1.0}


class Link:
    """Transmission state, kept separate from the scene."""

    def __init__(self):
        self.streaming = False
        self.drop = False  # diagnostics: number frames but never deliver them
        self.seq = 0
        self.sent = 0
        self.dropped: list[int] = []
        self.pending = None
        self.attempts = 0
        self.error = ""
        self.note = ""
        self.stages = {}
        self.document = None
        self.timeline = []  # recent per-frame timings for diagnostics


link = Link()

# Real recordings of the three people held out from training and validation.
UNSEEN = (11, 12, 13)
POSITION = {"back": 1, "right": 2, "left": 3}
LABEL = {"back": "Supine", "right": "Right", "left": "Left"}
FIRST_ROW = 10  # skip the first seconds, while the person settles
TOUR = [(subject, posture) for subject in UNSEEN for posture in ("back", "right", "left")]
CLIP_FRAMES = 8  # seconds each recording plays during the automatic tour


class Playback:
    def __init__(self):
        self.mode = "bed"  # or "recordings"
        self.subject = 12
        self.posture = "back"
        self.row = FIRST_ROW
        self.cache = {}
        self.auto = False  # automatic tour through every unseen person and posture
        self.played = 0  # frames played from the current recording during the tour

    def frames(self):
        key = (self.subject, self.posture)
        if key not in self.cache:
            self.cache[key] = recording(self.subject, POSITION[self.posture]).astype(int)
        return self.cache[key]

    def current(self):
        frames = self.frames()
        if self.row >= len(frames) - 2:
            self.row = FIRST_ROW
        return frames[self.row], self.row, len(frames)

    def advance(self):
        self.row += 1
        if self.row >= len(self.frames()) - 2:
            self.row = FIRST_ROW
        if self.auto:
            self.played += 1
            if self.played >= CLIP_FRAMES:
                i = TOUR.index((self.subject, self.posture)) if (self.subject, self.posture) in TOUR else -1
                self.subject, self.posture = TOUR[(i + 1) % len(TOUR)]
                self.row, self.played = FIRST_ROW, 0

    def start_tour(self):
        self.auto = True
        self.subject, self.posture = TOUR[0]
        self.row, self.played = FIRST_ROW, 0


playback = Playback()
receipts: dict[str, dict] = {}
preview = {"counts": [0] * 2048, "truth": {}, "measure": measure(np.zeros(2048)), "field": None}


def scene_json(mat, person, posture):
    return dict(
        bed=dict(w=BED_W, l=BED_L),
        mat=None
        if mat is None
        else dict(x=mat.x, y=mat.y, w=MAT_W, l=MAT_L, px=PX, py=PY, rows=32, cols=64),
        person=None
        if person is None
        else dict(x=person.x, y=person.y, theta=person.theta, roll=person.roll),
        posture=posture,
    )


def envelope(mat, person, truth):
    """Is the scene inside the conditions the CNN was trained and checked on?"""
    if mat is None:
        return dict(ok=False, reasons=["No mat on the bed, so there is no reading."])
    if person is None:
        return dict(ok=True, reasons=["Empty mat. The model is not run on zero load."])
    reasons = []
    cov = truth.get("coverage") or 0
    if cov < 0.97:
        reasons.append(f"{(1 - cov) * 100:.0f}% of body load is off the sensing area.")
    turn = (person.theta + 180) % 360 - 180
    if abs(turn) > 5:
        reasons.append(f"Body turned {abs(turn):.0f}° from the mat's long axis.")
    cx = mat.x + MAT_W / 2
    cy = mat.y + MAT_L / 2
    off_x = person.x - cx
    off_y = person.y - (mat.y + 0.89)
    if abs(off_x) > 0.06:
        reasons.append(f"Pelvis {abs(off_x) * 100:.0f} cm from the mat's centre line.")
    if abs(off_y) > 0.08:
        reasons.append(f"Pelvis {abs(off_y) * 100:.0f} cm from the usual hip position.")
    if 0.05 < abs(person.roll) < 0.95:
        reasons.append("Mid-roll. The CNN only learned settled postures.")
    del cy
    return dict(ok=not reasons, reasons=reasons)


def compute_preview():
    mat, person, posture = scene.snapshot()
    if playback.mode == "recordings":
        with lock:
            grid, row, total = playback.current()
            grid = grid.copy()
        with lock:
            preview.update(
                counts=grid.ravel().tolist(),
                truth=dict(on_bed=True, coverage=None),
                measure=measure(grid),
                field=[0] * len(preview.get("field") or [0] * 3468),
                field_shape=preview.get("field_shape", [68, 51]),
                envelope=dict(
                    ok=True,
                    reasons=[
                        f"Real recording of subject {playback.subject}, one of three people "
                        "held out from training and validation. The CNN has never seen them."
                    ],
                ),
                scene=scene_json(mat, person, posture),
            )
        return
    if mat is None:
        counts = np.zeros((32, 64), dtype=int)
        truth = dict(on_bed=person is not None, coverage=None)
    else:
        counts, truth = sensor.read(person, mat)
    field = bed_field(person)
    with lock:
        preview.update(
            counts=counts.ravel().tolist(),
            truth=truth,
            measure=measure(counts),
            field=np.rint(field * 10).astype(int).ravel().tolist(),
            field_shape=list(field.shape),
            envelope=envelope(mat, person, truth),
            scene=scene_json(mat, person, posture),
        )


def payload(seq, mat, person, posture):
    counts, truth = sensor.read(person, mat)
    return dict(
        schema_version=2,
        source="interactive_virtual_mat",
        device=DEVICE,
        session=SESSION,
        seq=seq,
        captured_ms=time.time_ns() // 1000000,
        rows=32,
        cols=64,
        unit="mmHg",
        value_scale=0.1,
        values=counts.ravel().tolist(),
        mat=dict(
            x_m=round(mat.x, 4),
            y_m=round(mat.y, 4),
            pitch_x_m=PX,
            pitch_y_m=PY,
            bed_w_m=BED_W,
            bed_l_m=BED_L,
        ),
        simulator=dict(
            person_on_bed=person is not None,
            posture_selected=posture if person is not None else None,
            roll=round(person.roll, 3) if person else 0.0,
            x_m=round(person.x, 4) if person else None,
            y_m=round(person.y, 4) if person else None,
            theta_deg=round(person.theta, 1) if person else None,
            coverage=truth["coverage"],
            body_force_n=truth["body_force_n"],
            mat_force_n=truth["mat_force_n"],
        ),
    )


def recorded_payload(seq, grid, row, subject, posture, auto):
    return dict(
        schema_version=1,
        source="recorded_replay",
        device=DEVICE,
        session=SESSION,
        seq=seq,
        captured_ms=time.time_ns() // 1000000,
        rows=32,
        cols=64,
        values=grid.ravel().tolist(),
        recording=f"S{subject}-{POSITION[posture]}",
        row=int(row),
        recorded_label=LABEL[posture],
        playlist="tour" if auto else "single",
    )


def send(frame):
    reply = requests.post(
        API_URL + "/frames",
        json=frame,
        timeout=8,
        headers={"Authorization": "Bearer " + os.environ["TEXTILE_TOKEN"]},
    )
    if reply.status_code >= 400:
        detail = reply.json().get("detail", reply.text) if reply.content else ""
        raise HTTPException(reply.status_code, str(detail)[:300])
    return reply.json()


async def animate():
    last = time.monotonic()
    tick_at = last
    while True:
        await asyncio.sleep(1 / 30)
        now = time.monotonic()
        dt, last = now - last, now
        with lock:
            p = scene.person
            if p is not None:
                goal = TARGET[scene.posture]
                step = dt / ROLL_SECONDS
                if abs(goal - p.roll) <= step:
                    p.roll = goal
                elif goal > p.roll:
                    p.roll += step
                else:
                    p.roll -= step
                p.breath = (p.breath + dt * 2 * math.pi / 4.0) % (2 * math.pi)
            # Recordings were sampled at 1 Hz; play them back at that rate.
            if playback.mode == "recordings" and now - tick_at >= 1 / RATE_HZ and not link.streaming:
                playback.advance()
                tick_at = now


async def previewer():
    while True:
        started = time.monotonic()
        await asyncio.to_thread(compute_preview)
        await asyncio.sleep(max(0.02, 0.066 - (time.monotonic() - started)))


async def transmitter():
    while True:
        started = time.monotonic()
        try:
            await asyncio.to_thread(tick)
        except Exception as exc:  # keep the loop alive whatever happens
            link.error = f"Unexpected sender error: {exc}"
        await asyncio.sleep(max(0.05, 1 / RATE_HZ - (time.monotonic() - started)))


def tick():
    mat, person, posture = scene.snapshot()
    if not link.streaming:
        return
    if playback.mode == "recordings" and link.pending is None:
        with lock:
            # Label the frame with the recording it came from *before* the
            # playlist moves on, so a frame and its label always belong together.
            grid, row, _ = playback.current()
            source = (playback.subject, playback.posture, playback.auto)
            playback.advance()
        link.pending = recorded_payload(link.seq, grid, row, *source)
        link.attempts = 0
        link.stages = dict(sensor=dict(seq=link.seq, captured_ms=link.pending["captured_ms"]))
    elif mat is None and playback.mode == "bed":
        link.note = "Place the mat on the bed to take readings."
        return
    link.note = ""
    if link.pending is None and playback.mode == "bed":
        link.pending = payload(link.seq, mat, person, posture)
        link.attempts = 0
        link.stages = dict(
            sensor=dict(
                seq=link.seq,
                captured_ms=link.pending["captured_ms"],
                peak_mmhg=max(link.pending["values"]) / 10,
            )
        )
    frame = link.pending
    if link.drop:
        link.dropped = (link.dropped + [frame["seq"]])[-50:]
        link.stages["python"] = dict(status="lost", detail="Link down: frame never sent")
        link.pending = None
        link.seq += 1
        return
    link.attempts += 1
    t0 = time.perf_counter()
    try:
        reply = send(frame)
    except HTTPException as exc:
        if exc.status_code < 500:
            link.streaming = False
            link.error = f"Python rejected frame {frame['seq']} ({exc.status_code}): {exc.detail}"
            link.stages["python"] = dict(status="rejected", detail=link.error)
            return
        return retry(f"Python service error {exc.status_code}: {exc.detail}")
    except requests.RequestException as exc:
        return retry(f"Python service unreachable ({type(exc).__name__})")
    round_trip = (time.perf_counter() - t0) * 1000
    link.stages["python"] = dict(
        status=reply["status"],
        round_trip_ms=round(round_trip, 1),
        inference_ms=round(reply.get("inference_ms", 0), 2),
        transaction_ms=round(reply.get("transaction_ms", 0), 1),
    )
    try:
        saved = latest_ref.get(timeout=5).to_dict() or {}
    except Exception as exc:
        return retry(f"Could not read Firestore back ({type(exc).__name__})")
    if saved.get("seq") != frame["seq"]:
        return retry("Firestore latest differs from the frame just sent")
    link.document = saved
    link.stages["firestore"] = dict(
        frame_id=saved["frame_id"],
        processed_ms=saved["processed_ms"],
        prediction=saved.get("prediction"),
    )
    link.timeline = (
        link.timeline
        + [
            dict(
                seq=frame["seq"],
                captured_ms=frame["captured_ms"],
                latency_ms=saved.get("latency_ms"),
                inference_ms=saved.get("inference_ms"),
                round_trip_ms=round(round_trip, 1),
                attempts=link.attempts,
            )
        ]
    )[-120:]
    link.pending = None
    link.error = ""
    link.seq += 1
    link.sent += 1
    if link.sent >= CAP:
        link.streaming = False
        link.note = f"Paused automatically after {CAP} frames. Start again to continue."


def retry(message):
    link.error = f"{message}. Retrying frame {link.pending['seq']} (attempt {link.attempts})."
    link.stages["python"] = dict(status="retrying", detail=link.error)


remote = {}  # last control request a phone sent, for the console to display
STARTED_MS = time.time_ns() // 1000000


def watch_controls():
    """Act on start/pause/source requests from signed-in phones (rules-checked)."""

    def changed(docs, changes, read_time):
        for change in changes:
            data = change.document.to_dict() or {}
            stamp = data.get("requested_at")
            if stamp is None or stamp.timestamp() * 1000 < STARTED_MS:
                continue  # ignore requests made before this console started
            key = (change.document.id, stamp.timestamp())
            if remote.get("key") == key:
                continue
            action = data.get("action")
            if action in ("start", "pause"):
                if action == "start":
                    with lock:  # a phone cannot drag the mat, so put it on the bed
                        if playback.mode == "bed" and scene.mat is None:
                            scene.mat = MatPlacement()
                apply_transmit(action)
            elif action == "source" and data.get("mode") in ("bed", "recordings"):
                # Choosing a source on the phone plays it from the beginning.
                apply_source(data["mode"], data.get("subject"), data.get("posture"))
                with lock:
                    if not playback.auto:
                        playback.row = FIRST_ROW
                    link.pending = None
                apply_transmit("start")
            remote.update(
                key=key,
                action=action,
                mode=data.get("mode"),
                subject=data.get("subject"),
                posture=data.get("posture"),
                device=data.get("device", "a phone"),
                at_ms=int(stamp.timestamp() * 1000),
            )

    return session_ref.collection("controls").on_snapshot(changed)


def watch_receipts():
    def changed(docs, changes, read_time):
        for d in docs:
            data = d.to_dict() or {}
            stamp = data.get("rendered_at")
            if stamp is not None:
                data["rendered_ms"] = int(stamp.timestamp() * 1000)
                data.pop("rendered_at")
            receipts[d.id] = data

    return session_ref.collection("viewers").on_snapshot(changed)


@asynccontextmanager
async def lifespan(app):
    doc = (await asyncio.to_thread(latest_ref.get, timeout=10)).to_dict() or {}
    link.seq = doc.get("seq", -1) + 1
    link.document = doc or None
    watcher = await asyncio.to_thread(watch_receipts)
    controls = await asyncio.to_thread(watch_controls)
    tasks = [asyncio.create_task(f()) for f in (animate, previewer, transmitter)]
    try:
        yield
    finally:
        watcher.unsubscribe()
        controls.unsubscribe()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(lifespan=lifespan, title="TextileSense virtual bed console")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])


def same_origin(request: Request):
    if request.headers.get("origin") != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Operate the bed from its local console page")


class SceneOp(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal[
        "place_mat", "move_mat", "remove_mat", "place_person", "move_person",
        "rotate", "posture", "get_up", "centre",
    ]
    x: float | None = Field(default=None, ge=-1, le=4)
    y: float | None = Field(default=None, ge=-1, le=4)
    theta: float | None = Field(default=None, ge=-720, le=720)
    posture: Literal["back", "left", "right"] | None = None


@app.post("/api/scene")
def change_scene(op: SceneOp, request: Request):
    same_origin(request)
    with lock:
        if op.op in ("place_mat", "move_mat"):
            scene.mat = MatPlacement(op.x, op.y).clamp()
        elif op.op == "remove_mat":
            scene.mat = None
        elif op.op in ("place_person", "move_person"):
            if scene.person is None:
                if op.op == "move_person":
                    raise HTTPException(409, "Place the person on the bed first")
                scene.person = Person(roll=TARGET[scene.posture])
            scene.person.x, scene.person.y = op.x, op.y
            clamp_person(scene.person)
        elif op.op == "rotate":
            if scene.person is None:
                raise HTTPException(409, "Place the person on the bed first")
            scene.person.theta = (op.theta + 180) % 360 - 180
            clamp_person(scene.person)
        elif op.op == "posture":
            scene.posture = op.posture
        elif op.op == "get_up":
            scene.person = None
            scene.posture = "back"
        elif op.op == "centre":
            if scene.person is None or scene.mat is None:
                raise HTTPException(409, "Place the mat and the person first")
            scene.person.theta = 0.0
            scene.person.x = scene.mat.x + MAT_W / 2
            scene.person.y = scene.mat.y + 0.89
            clamp_person(scene.person)
        scene.version += 1
        return scene_json(scene.mat, scene.person, scene.posture)


class SourceOp(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["bed", "recordings"]
    subject: Literal[11, 12, 13] | None = None
    posture: Literal["back", "left", "right"] | None = None


def apply_source(mode, subject=None, posture=None):
    with lock:
        if mode == "recordings" and subject is None and posture is None:
            # No particular recording asked for: tour all of them automatically.
            playback.mode = mode
            playback.start_tour()
            link.pending = None
            if scene.mat is None:
                scene.mat = MatPlacement()
            return dict(mode=mode, subject=playback.subject, posture=playback.posture, auto=True)
        if mode == "recordings":
            playback.auto = False
        changed = mode != playback.mode
        playback.mode = mode
        if subject is not None and subject != playback.subject:
            playback.subject, changed = subject, True
        if posture is not None and posture != playback.posture:
            playback.posture, changed = posture, True
        if changed:
            playback.row = FIRST_ROW
            link.pending = None  # never send a frame captured from the other source
        if mode == "recordings" and scene.mat is None:
            scene.mat = MatPlacement()  # the recording is a full mat reading
    return dict(mode=playback.mode, subject=playback.subject, posture=playback.posture, auto=playback.auto)


def apply_transmit(action):
    if action == "start":
        if not link.streaming:
            link.sent = 0
        link.streaming = True
        link.error = ""
    elif action == "pause":
        link.streaming = False
    elif action == "drop_link":
        link.drop = True
    else:
        link.drop = False


@app.post("/api/source")
def change_source(op: SourceOp, request: Request):
    same_origin(request)
    return apply_source(op.mode, op.subject, op.posture)


class TransmitOp(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["start", "pause", "drop_link", "restore_link"]


@app.post("/api/transmit")
def transmit(op: TransmitOp, request: Request):
    same_origin(request)
    apply_transmit(op.action)
    return {"streaming": link.streaming, "drop": link.drop}


def doc_summary(doc, full=False):
    if not doc:
        return None
    keys = [
        "frame_id", "seq", "source", "captured_ms", "received_ms", "processed_ms",
        "latency_ms", "prediction", "labels", "scores", "model", "model_status",
        "measurement", "input_flags", "validation", "simulator", "mat", "count",
        "missing", "duplicates", "out_of_order", "gap_frames", "resumed", "digest",
        "unit", "value_scale", "inference_ms", "api_ms", "model_input", "delayed",
        "recording", "row", "recorded_label", "playlist",
    ]
    out = {k: doc.get(k) for k in keys if k in doc}
    out["values"] = doc.get("values")
    if full:
        out = dict(doc)
    return out


@app.get("/api/live")
def live():
    with lock:
        state = dict(preview)
    phones = sorted(receipts.items(), key=lambda kv: -kv[1].get("rendered_ms", 0))
    return dict(
        **state,
        link=dict(
            streaming=link.streaming,
            drop=link.drop,
            next_seq=link.seq,
            sent=link.sent,
            cap=CAP,
            pending=link.pending["seq"] if link.pending else None,
            attempts=link.attempts,
            error=link.error,
            note=link.note,
            stages=link.stages,
            dropped=link.dropped[-10:],
            rate_hz=RATE_HZ,
        ),
        frame=doc_summary(link.document),
        source=dict(
            mode=playback.mode,
            subject=playback.subject,
            posture=playback.posture,
            row=playback.row,
            rows=len(playback.frames()) if playback.mode == "recordings" else None,
            auto=playback.auto,
            tour_step=(TOUR.index((playback.subject, playback.posture)) + 1) if playback.auto else None,
            tour_len=len(TOUR),
            clip_left=CLIP_FRAMES - playback.played if playback.auto else None,
            unseen=list(UNSEEN),
        ),
        phones=[dict(uid=k[:6], **v) for k, v in phones[:3]],
        remote={k: v for k, v in remote.items() if k != "key"} or None,
        server_ms=time.time_ns() // 1000000,
        project=os.environ.get("TEXTILE_PROJECT"),
        session=SESSION,
        hosted=not local_demo,
    )


@app.get("/api/body")
def body_geometry():
    """The segment geometry the contact model uses, so the drawing matches it."""

    def rows(table):
        return [dict(b0=r[0], a0=r[1], b1=r[2], a1=r[3], w=r[5]) for r in table.tolist()]

    return dict(back=rows(SUPINE_T), right=rows(RIGHT_T), left=rows(LEFT_T))


@app.get("/api/behavior")
def behavior():
    path = Path("evidence/interactive/model-behavior.json")
    if not path.exists():
        raise HTTPException(404, "Run python -m proof.model_behavior to create it")
    return FileResponse(path)


@app.get("/api/diagnostics")
def diagnostics():
    return dict(
        document=doc_summary(link.document, full=True),
        timeline=link.timeline,
        dropped=link.dropped,
        receipts=receipts,
        session=SESSION,
        device=DEVICE,
        project=os.environ.get("TEXTILE_PROJECT"),
        cap=CAP,
    )


@app.get("/")
def console():
    return FileResponse(STATIC / "index.html")


@app.get("/diagnostics")
def diagnostics_page():
    return FileResponse(STATIC / "diagnostics.html")


@app.get("/console")
def database_console():
    if local_demo:
        url = f"http://127.0.0.1:4100/firestore/default/data/sessions/{SESSION}/state/latest"
    else:
        url = (
            "https://console.firebase.google.com/project/"
            + os.environ["TEXTILE_PROJECT"]
            + f"/firestore/databases/-default-/data/~2Fsessions~2F{SESSION}~2Fstate~2Flatest"
        )
    return RedirectResponse(url)


@app.get("/monitor")
def monitor():
    if not (DIST / "index.html").exists():
        raise HTTPException(404, "Export the Expo web build to use the browser monitor")
    return FileResponse(DIST / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="console assets")
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST), name="Expo assets")
