import argparse
import logging
import os
import time

import requests

from dataset import recording


def frame(values, seq, s, p, row, session):
    return dict(
        device="mat01",
        session=session,
        seq=seq,
        captured_ms=time.time_ns() // 1000000,
        rows=32,
        cols=64,
        values=values.astype(int).ravel().tolist(),
        source="recorded_replay",
        recording=f"S{s}-{p}",
        row=row,
        schema_version=1,
    )


def post(payload):
    for attempt in range(4):
        try:
            reply = requests.post(
                os.getenv("TEXTILE_API_URL", "http://127.0.0.1:8000") + "/frames",
                json=payload,
                timeout=5,
                headers={"Authorization": "Bearer " + os.environ["TEXTILE_TOKEN"]},
            )
            reply.raise_for_status()
            return reply.json()
        except requests.RequestException as exc:
            if attempt == 3 or (
                exc.response is not None and exc.response.status_code < 500
            ):
                raise
            logging.warning(
                "Retrying frame %s/%s after %s (attempt %d of 4)",
                payload["session"],
                payload["seq"],
                type(exc).__name__,
                attempt + 1,
            )
            time.sleep(0.25 * 2**attempt)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", default="demo")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--pause", action="store_true")
    args = parser.parse_args()
    seq = args.start
    for position in (1, 2, 3):
        frames = recording(11, position)
        for row in range(35, 47):
            start = time.monotonic()
            print(
                post(frame(frames[row], seq, 11, position, row, args.session)),
                flush=True,
            )
            seq += 1
            time.sleep(max(0, 1 - (time.monotonic() - start)))
        if args.pause and position == 1:
            time.sleep(5)
