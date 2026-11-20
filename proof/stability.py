"""Paced replay with independent Firestore read-back and change subscription."""

import argparse
import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path

import numpy as np
import psutil

from dataset import recording
from replay import frame, post
from store import database

OUT = Path("evidence/live_test")


def run(count, label):
    if os.getenv("TEXTILE_PROJECT", "demo-textilesense") != "demo-textilesense":
        raise ValueError("Run stability workloads only on the emulator")
    sid = label + "-" + uuid.uuid4().hex[:8]
    db = database()
    session = db.document("sessions/" + sid)
    session.set({"readers": [], "device": "mat01"})
    latest = session.collection("state").document("latest")
    seen = set()
    ready = threading.Event()

    def changed(docs, changes, read_time):
        for d in docs:
            if d.exists:
                seen.add(d.get("seq"))
        ready.set()

    watch = latest.on_snapshot(changed)
    assert ready.wait(10)
    manifest = dict(
        line.split()[::-1]
        for line in Path("data/SHA256SUMS.txt").read_text().splitlines()
    )
    source = []
    for subject in (11, 12, 13):
        for pos in (1, 2, 3):
            file = f"experiment-i/S{subject}/{pos}.txt"
            assert (
                hashlib.sha256((Path("data") / file).read_bytes()).hexdigest()
                == manifest[file]
            )
            source.extend(
                (subject, pos, row, a) for row, a in enumerate(recording(subject, pos))
            )
    rows = []
    process = (
        psutil.Process(int(os.environ["TEXTILE_API_PID"]))
        if "TEXTILE_API_PID" in os.environ
        else None
    )
    if process:
        process.cpu_percent()
    started = time.monotonic()
    OUT.mkdir(exist_ok=True, parents=True)
    try:
        with (OUT / (label + ".jsonl")).open("w") as log:
            for seq in range(count):
                subject, pos, row, a = source[seq]
                payload = frame(a, seq, subject, pos, row, sid)
                result = post(payload)
                snap = latest.get().to_dict()
                assert result["status"] == "accepted" and all(
                    snap[k] == v for k, v in payload.items()
                )
                assert (
                    snap["frame_id"] == result["frame_id"]
                    and snap["prediction"]
                    == result["prediction"]
                    == snap["labels"][np.argmax(snap["scores"])]
                )
                assert (
                    snap["received_ms"] >= snap["captured_ms"]
                    and snap["count"] == seq + 1
                )
                measurement = {
                    k: snap[k]
                    for k in (
                        "frame_id",
                        "recording",
                        "row",
                        "digest",
                        "captured_ms",
                        "received_ms",
                        "processed_ms",
                        "prediction",
                        "scores",
                        "inference_ms",
                    )
                }
                measurement.update(
                    transaction_ms=result["transaction_ms"], readback=True
                )
                if process:
                    measurement.update(
                        api_cpu_percent=process.cpu_percent(),
                        api_rss_mib=process.memory_info().rss / 2**20,
                    )
                rows.append(measurement)
                log.write(json.dumps(measurement) + "\n")
                log.flush()
                print(
                    f"{snap['frame_id']} received and validated | CNN {snap['prediction']} | Firestore verified",
                    flush=True,
                )
                time.sleep(max(0, started + seq + 1 - time.monotonic()))
        elapsed = time.monotonic() - started
        assert seen == set(range(count))
        assert snap["missing"] == snap["duplicates"] == 0
        summary = dict(
            session=sid,
            sent=count,
            received=snap["count"],
            published=len(rows),
            listener_frames=len(seen),
            dropped=0,
            rejected=0,
            elapsed_s=elapsed,
            input_hz=count / elapsed,
        )
        for k in ("inference_ms", "transaction_ms", "api_cpu_percent", "api_rss_mib"):
            if k in rows[0]:
                summary[k] = dict(
                    zip(
                        ("median", "p95", "max"),
                        np.percentile([r[k] for r in rows], [50, 95, 100]),
                    )
                )
        (OUT / (label + ".json")).write_text(json.dumps(summary, indent=2))
    finally:
        watch.unsubscribe()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("label", choices=["two-minute", "ten-minute"])
    label = parser.parse_args().label
    run(120 if label == "two-minute" else 600, label)
