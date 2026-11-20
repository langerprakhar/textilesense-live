import hashlib
import hmac
import json
import logging
import os
import time
from typing import Annotated, Literal

import numpy as np
import torch
from fastapi import FastAPI, Header, HTTPException
from google.api_core.exceptions import GoogleAPICallError, RetryError
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import BaseModel, ConfigDict, Field

from model import PostureCNN, inputs
from store import database

ID = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]
Value = Annotated[int, Field(ge=0, le=65535, strict=True)]


class Reading(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device: ID
    session: ID
    seq: Annotated[int, Field(ge=0, le=1000000)]
    captured_ms: Annotated[int, Field(gt=0)]
    rows: Literal[32]
    cols: Literal[64]
    values: Annotated[list[Value], Field(min_length=2048, max_length=2048)]
    schema_version: Literal[1]


class RecordedReading(Reading):
    source: Literal["recorded_replay", "recorded pressure mat"]
    recording: ID
    row: Annotated[int, Field(ge=0)]


class VirtualReading(Reading):
    source: Literal["virtual_pressure_mat"]
    scenario: Literal["empty", "back", "left", "right"]


def now():
    return time.time_ns() // 1000000


db = database()
token = os.environ["TEXTILE_TOKEN"]
if len(token) < 24:
    raise RuntimeError("Set a random ingestion token of at least 24 characters")
checkpoint = torch.load(
    os.environ.get("TEXTILE_MODEL", "model.pt"), map_location="cpu", weights_only=True
)
cfg = checkpoint["config"]
net = PostureCNN().eval()
net.load_state_dict(checkpoint["weights"])
torch.set_num_threads(1)
app = FastAPI(title="TextileSense Live")
HISTORY = 32


@app.post("/frames")
def ingest(
    r: RecordedReading | VirtualReading, authorization: str = Header(default="")
):
    if not hmac.compare_digest(authorization, "Bearer " + token):
        raise HTTPException(401)
    received = now()
    if r.captured_ms > received + 1000:
        raise HTTPException(422, "capture clock is ahead")
    payload = r.model_dump()
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    doc = db.document(f"sessions/{r.session}")
    latest = doc.collection("state").document("latest")
    inference_start = time.perf_counter()
    unloaded = isinstance(r, VirtualReading) and max(r.values) == 0
    scores = []
    try:
        if not unloaded:
            with torch.inference_mode():
                scores = (
                    net(inputs(np.array(r.values), cfg["cap"])).softmax(1)[0].tolist()
                )
    except RuntimeError:
        logging.exception("Inference failed for %s/%d", r.session, r.seq)
        raise HTTPException(503, "Posture model unavailable")
    inference_ms = (time.perf_counter() - inference_start) * 1000

    @firestore.transactional
    def persist(tx):
        meta = doc.get(transaction=tx).to_dict()
        if not meta or meta.get("device") != r.device:
            raise HTTPException(403, "device/session mismatch")
        old = latest.get(transaction=tx).to_dict() or {}
        last = old.get("seq", -1)
        if r.seq <= last:
            event = (
                doc.collection("events")
                .where(filter=FieldFilter("seq", "==", r.seq))
                .limit(1)
            )
            found = next(iter(event.stream(transaction=tx)), None)
            if found and found.get("digest") != digest:
                raise HTTPException(409, "sequence already used for different content")
            key = "duplicates" if found else "out_of_order"
            tx.update(latest, {key: firestore.Increment(1)})
            return {"status": key, "seq": r.seq}
        count = old.get("count", 0) + 1
        processed = now()
        gap = received - old.get("received_ms", received)
        snapshot = dict(
            **payload,
            digest=digest,
            inference_ms=inference_ms,
            frame_id=f"{r.session}/{r.seq}",
            scores=scores,
            prediction="Empty bed"
            if unloaded
            else cfg["labels"][int(np.argmax(scores))],
            labels=[] if unloaded else cfg["labels"],
            model=cfg["version"],
            count=count,
            first_ms=old.get("first_ms", received),
            received_ms=received,
            processed_ms=processed,
            latency_ms=processed - r.captured_ms,
            delayed=received - r.captured_ms > 2000,
            resumed=gap > 3500,
            missing=old.get("missing", 0) + r.seq - last - 1,
            duplicates=old.get("duplicates", 0),
            out_of_order=old.get("out_of_order", 0),
        )
        tx.set(latest, snapshot)
        tx.set(doc.collection("events").document(str((count - 1) % HISTORY)), snapshot)
        return {
            "status": "accepted",
            "frame_id": snapshot["frame_id"],
            "latency_ms": snapshot["latency_ms"],
            "prediction": snapshot["prediction"],
            "inference_ms": inference_ms,
        }

    write_start = time.perf_counter()
    try:
        result = persist(db.transaction())
    except (GoogleAPICallError, RetryError):
        logging.exception("Firestore transaction failed for %s/%d", r.session, r.seq)
        raise HTTPException(503, "Firestore unavailable")
    result["transaction_ms"] = (time.perf_counter() - write_start) * 1000
    return result
