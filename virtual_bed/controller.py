"""Loopback-only operator panel. All mat writes go through the normal HTTP API."""

import asyncio
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware

from replay import post
from store import database
from virtual_bed.sensor import Mat

SESSION = "virtual-bed"
DEVICE = "virtual-mat-01"
DIST = Path(os.getenv("VIRTUAL_WEB_DIST", ".cache/virtual-web"))
latest = database().document(f"sessions/{SESSION}/state/latest")
mat = Mat()
pose = "empty"
remaining = 0
error = ""
pending = None
document = None
local_demo = os.environ.get("TEXTILE_PROJECT") == "demo-textilesense-bed"
MAX_FRAMES = 120 if local_demo else 30


async def stream(number):
    global remaining, pending, error, document
    while True:
        started = time.monotonic()
        if remaining:
            if pending is None:
                values = mat.sample(pose)
                pending = dict(
                    schema_version=1,
                    source="virtual_pressure_mat",
                    device=DEVICE,
                    session=SESSION,
                    seq=number,
                    captured_ms=time.time_ns() // 1000000,
                    scenario=pose,
                    rows=32,
                    cols=64,
                    values=values.ravel().tolist(),
                )
            try:
                reply = await asyncio.to_thread(post, pending)
                if reply["status"] not in ("accepted", "duplicates"):
                    raise RuntimeError(
                        f"Unexpected ingestion response: {reply['status']}"
                    )
                saved = (await asyncio.to_thread(latest.get, timeout=5)).to_dict()
                if not saved or saved["seq"] != number:
                    raise RuntimeError(
                        "Current Firestore frame differs from the sent frame"
                    )
                document = saved
            except Exception as exc:
                error = f"Transmission stopped: {exc}. Resume to retry this frame."
                remaining = 0
            else:
                pending = None
                number += 1
                remaining = max(0, remaining - 1)
                error = ""
        await asyncio.sleep(max(0.05, 1 - (time.monotonic() - started)))


@asynccontextmanager
async def lifespan(app):
    global document
    document = (await asyncio.to_thread(latest.get, timeout=5)).to_dict()
    task = asyncio.create_task(stream((document or {}).get("seq", -1) + 1))
    try:
        yield
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


app = FastAPI(lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])


class Action(BaseModel):
    action: Literal["start", "pause", "empty", "back", "left", "right"]


@app.post("/action")
async def control(command: Action, request: Request):
    global remaining, pose
    if request.headers.get("origin") != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Operate the sensor from its local control page")
    if command.action == "start":
        if not remaining:
            remaining = MAX_FRAMES
    elif command.action == "pause":
        remaining = 0
    else:
        pose = command.action
    return {"pose": pose, "remaining": remaining}


@app.get("/reading")
def reading():
    return {"document": document, "pose": pose, "remaining": remaining, "error": error}


@app.get("/")
def panel():
    return FileResponse("virtual_bed/panel.html")


@app.get("/console")
def database_console():
    if local_demo:
        url = "http://127.0.0.1:4100/firestore/default/data/sessions/virtual-bed/state/latest"
    else:
        url = (
            "https://console.firebase.google.com/project/"
            + os.environ["TEXTILE_PROJECT"]
            + "/firestore/databases/-default-/data"
        )
    return RedirectResponse(url)


@app.get("/monitor")
def monitor():
    return FileResponse(DIST / "index.html")


app.mount("/", StaticFiles(directory=DIST), name="Expo assets")
