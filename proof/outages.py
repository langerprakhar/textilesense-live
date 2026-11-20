"""Inject a database outage into an isolated live API, then exercise a model failure."""

import concurrent.futures
import contextlib
import os
import select
import socket
import socketserver
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from unittest.mock import patch

import requests
from fastapi.testclient import TestClient

if os.getenv("TEXTILE_PROJECT", "demo-textilesense") != "demo-textilesense":
    raise RuntimeError("Emulator required")
import api
from dataset import recording
from replay import frame, post


class Relay(socketserver.BaseRequestHandler):
    def handle(self):
        if not self.server.available.is_set():
            return
        with socket.create_connection(("127.0.0.1", 8080), timeout=2) as upstream:
            pipes = {upstream: self.request, self.request: upstream}
            try:
                while self.server.available.is_set():
                    for src in select.select(list(pipes), [], [], 0.15)[0]:
                        data = src.recv(65536)
                        if not data:
                            return
                        pipes[src].sendall(data)
            except OSError:
                return


def run():
    sid = "outage-" + uuid.uuid4().hex[:8]
    session = api.db.document("sessions/" + sid)
    session.set({"device": "mat01", "readers": []})
    latest = session.collection("state").document("latest")

    def sample(seq):
        return frame(recording(11, 1)[35 + seq], seq, 11, 1, 35 + seq, sid)

    with contextlib.ExitStack() as cleanup:
        relay = cleanup.enter_context(
            socketserver.ThreadingTCPServer(("127.0.0.1", 0), Relay)
        )
        relay.daemon_threads = True
        relay.available = threading.Event()
        relay.available.set()
        threading.Thread(target=relay.serve_forever, daemon=True).start()
        cleanup.callback(relay.shutdown)
        # Uvicorn inherits a bound socket to avoid collisions with other demos.
        sock = cleanup.enter_context(socket.socket())
        sock.bind(("127.0.0.1", 0))
        url = "http://127.0.0.1:" + str(sock.getsockname()[1])
        env = dict(os.environ, TEXTILE_EMULATOR_PORT=str(relay.server_address[1]))
        log = cleanup.enter_context(Path("evidence/live_test/outage-api.log").open("w"))
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api:app", "--fd", str(sock.fileno())],
            pass_fds=[sock.fileno()],
            env=env,
            stdout=log,
            stderr=log,
        )
        cleanup.callback(lambda: (proc.terminate(), proc.wait(timeout=12)))
        for _ in range(100):
            try:
                if requests.get(url + "/openapi.json", timeout=0.3).ok:
                    break
            except requests.ConnectionError:
                pass
            time.sleep(0.1)
        with patch.dict(os.environ, TEXTILE_API_URL=url):
            assert post(sample(0))["status"] == "accepted"
            relay.available.clear()
            time.sleep(0.4)
            f = sample(1)
            with concurrent.futures.ThreadPoolExecutor(1) as ex:
                start = time.monotonic()
                future = ex.submit(post, f)
                time.sleep(6)
                assert latest.get().get("seq") == 0 and not future.done()
                relay.available.set()
                reply = future.result(timeout=25)
                assert reply["status"] in ("accepted", "duplicates")
                print(
                    f"Database relay offline 6 seconds. Last document stayed at 0. Request recovered in {time.monotonic() - start:.2f}s.",
                    flush=True,
                )
            assert post(sample(2))["status"] == "accepted"
            s = latest.get().to_dict()
            assert (
                s["seq"] == 2
                and s["count"] == 3
                and len(list(session.collection("events").stream())) == 3
            )
            print("PASS three unique commits after connectivity returned", flush=True)
    headers = {"Authorization": "Bearer " + os.environ["TEXTILE_TOKEN"]}
    client = TestClient(api.app)
    f = sample(3)
    with patch.object(
        api.net, "forward", side_effect=RuntimeError("controlled CNN failure")
    ):
        res = client.post("/frames", json=f, headers=headers)
        assert (
            res.status_code == 503
            and res.json()["detail"] == "Posture model unavailable"
        )
        assert latest.get().get("seq") == 2
    assert (
        client.post("/frames", json=f, headers=headers).json()["status"] == "accepted"
    )
    print(
        "PASS simulated model exception, 503 response, last frame preserved, same input accepted after restore"
    )


if __name__ == "__main__":
    run()
