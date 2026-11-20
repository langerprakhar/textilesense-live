"""Optional single-sensor transport demo, independent of the mat classifier."""

import hmac
import os
from typing import Literal
from fastapi import FastAPI, Header, HTTPException
from google.cloud import firestore
from pydantic import BaseModel, Field
from store import database

db = database()
token = os.environ["TEXTILE_PROBE_TOKEN"]
if len(token) < 24:
    raise RuntimeError("Set a strong probe-only token")
app = FastAPI()


class Sample(BaseModel):
    source: Literal["software simulation", "physical FSR"]
    boot: str = Field(pattern=r"^[a-f0-9]{8}$")
    seq: int = Field(ge=0, le=4294967295)
    adc: int = Field(ge=0, le=4095)
    uptime_ms: int = Field(ge=0)


@app.post("/probe")
def probe(sample: Sample, authorization: str = Header(default="")):
    if not hmac.compare_digest(authorization, "Bearer " + token):
        raise HTTPException(401)
    key = "sim" if sample.source == "software simulation" else "fsr"
    db.document("devices/probe-" + key + "/state/latest").set(
        {**sample.model_dump(), "received": firestore.SERVER_TIMESTAMP}
    )
    return {"boot": sample.boot, "seq": sample.seq}
