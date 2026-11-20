"""Ten generated ADC values. This exercises transport only."""

import os
import secrets
import time
import requests

boot = secrets.token_hex(4)
for seq in range(10):
    sample = dict(
        source="software simulation",
        boot=boot,
        seq=seq,
        adc=seq * 300,
        uptime_ms=seq * 1000,
    )
    response = requests.post(
        "http://127.0.0.1:8010/probe",
        json=sample,
        headers={"Authorization": "Bearer " + os.environ["TEXTILE_PROBE_TOKEN"]},
        timeout=3,
    )
    response.raise_for_status()
    assert response.json() == {"boot": boot, "seq": seq}
    print(sample, flush=True)
    time.sleep(1)
