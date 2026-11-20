import json
import os
import time
import uuid

import numpy as np

from dataset import recording
from replay import frame, post
from store import database

if os.getenv("TEXTILE_PROJECT", "demo-textilesense") != "demo-textilesense":
    raise RuntimeError("This test writes only to the local demo emulator")


sid = "bench-" + uuid.uuid4().hex[:10]
ref = database().document("sessions/" + sid)
ref.set({"device": "mat01", "readers": []})
try:
    values = recording(11, 1)
    latencies = []
    start = time.monotonic()
    for i in range(48):
        begin = time.monotonic()
        res = post(frame(values[i], i, 11, 1, i, sid))
        assert res["status"] == "accepted"
        latencies.append(1000 * (time.monotonic() - begin))
    print(
        json.dumps(
            dict(
                frames=48,
                sequential_hz=48 / (time.monotonic() - start),
                http_ack_ms_p50_p95=np.percentile(latencies, [50, 95]).tolist(),
            ),
            indent=2,
        )
    )
finally:
    for group in ("state", "events"):
        for child in ref.collection(group).stream():
            child.reference.delete()
    ref.delete()
