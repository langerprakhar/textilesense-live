"""Record one continuous 90-second take of the actual Expo web client and replay."""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time
from collections import deque
from pathlib import Path

import numpy as np
from playwright.sync_api import expect, sync_playwright

from dataset import recording
from replay import frame, post
from store import database

OUT = Path("evidence/live_test")
PAGE = """<!doctype html><meta charset=utf-8><title>TextileSense Live demonstration</title>
<style>*{box-sizing:border-box}body{margin:0;display:grid;grid-template-columns:1fr 450px;background:#f4f4ee;color:#1b302f;font:20px system-ui;height:100vh}
main{padding:36px}h1{font-size:36px;margin:0 0 5px}h2{font-size:18px;margin:28px 0 6px}
p{line-height:1.45;margin:0}pre{white-space:pre-wrap;font:17px/1.55 monospace;margin:0;color:#184d48}iframe{width:100%;height:100%;border:0}
</style><main><h1>TextileSense Live</h1><p>Recorded pressure mat · local Firestore emulator</p>
<h2>Pressure readings</h2><pre id="source"></pre><h2>Python ingestion and CNN</h2><pre id="trace"></pre>
<h2>Latest Firestore document · read back after commit</h2><pre id="stored"></pre></main><iframe src="/"></iframe>"""


def run(headed=False, output=OUT):
    if os.getenv("TEXTILE_PROJECT", "demo-textilesense") != "demo-textilesense":
        raise ValueError("Recording requires the local emulator")
    db = database()
    latest = db.document("sessions/demo/state/latest")
    seq = (latest.get().to_dict() or {}).get("seq", -1) + 1
    recordings = {p: recording(11, p) for p in (1, 2, 3)}
    trace = deque(maxlen=4)
    measures = []
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        exe = os.getenv("CHROMIUM_PATH") or shutil.which("chromium")
        browser = pw.chromium.launch(executable_path=exe, headless=not headed)
        size = {"width": 1200, "height": 940}
        ctx = browser.new_context(
            viewport=size, record_video_dir=tmp, record_video_size=size
        )
        page = ctx.new_page()
        page.route(
            "**/presentation",
            lambda route: route.fulfill(content_type="text/html", body=PAGE),
        )
        page.goto(
            os.getenv("TEXTILE_WEB_URL", "http://127.0.0.1:8765") + "/presentation"
        )
        app = page.frame_locator("iframe")
        app.get_by_label("Password").fill(os.environ["DEMO_PASSWORD"])
        app.get_by_text("Sign in", exact=True).click()
        expect(app.get_by_text("Live monitoring", exact=True)).to_be_visible()

        def show(element, text):
            page.locator("#" + element).evaluate("(e,t)=>e.textContent=t", text)

        def source(pos, row):
            a = recordings[pos][row]
            show(
                "source",
                f"PmatData v1.0.0 · experiment-i/S11/{pos}.txt\nRow {row} · 32 × 64 cells\nGrid row 12, columns 20–27: {a[12, 20:28].astype(int).tolist()}",
            )

        source(1, 35)
        show("trace", "Replay starts at 00:15")
        show("stored", "sessions/demo/state/latest")
        # Single take. Trim initial sign-in and browser setup from the start only.
        video = page.video
        start = time.monotonic()
        recovery_start = None
        for second in range(90):
            page.wait_for_timeout(
                max(0, int((start + second - time.monotonic()) * 1000))
            )
            if second == 65:
                show("trace", "Replay paused · last committed frame retained")
            if second == 70:
                expect(app.get_by_text("Stale", exact=False).first).to_be_visible()
                assert latest.get().get("seq") == seq - 1
                page.screenshot(path=str(output / "demo-stale.png"))
            if 15 <= second < 65 or second >= 80:
                pos = 1 if second < 32 else 2 if second < 49 else 3
                row = 35 + (second - 15) % 16
                source(pos, row)
                payload = frame(recordings[pos][row], seq, 11, pos, row, "demo")
                if second == 80:
                    recovery_start = time.monotonic()
                result = post(payload)
                snap = latest.get().to_dict()
                assert (
                    snap["frame_id"] == result["frame_id"]
                    and snap["values"] == payload["values"]
                )
                expect(app.get_by_text(snap["frame_id"], exact=True)).to_be_visible()
                expect(
                    app.get_by_text("Live · Recorded pressure mat", exact=True)
                ).to_be_visible()
                measured = time.time_ns() / 1e6 - payload["captured_ms"]
                if second == 80:
                    recovery_ms = (time.monotonic() - recovery_start) * 1000
                    assert snap["resumed"]
                measures.append(measured)
                trace.append(
                    f"{snap['frame_id']}  validated → CNN {snap['prediction']} → committed"
                )
                show("trace", "\n".join(trace))
                show(
                    "stored",
                    f"sessions/demo/state/latest\nframe_id    {snap['frame_id']}\nsource      {snap['source']}\nprediction  {snap['prediction']}\nscores      {[round(v, 3) for v in snap['scores']]}\nmodel       {snap['model']}",
                )
                if second in (25, 40, 60):
                    page.screenshot(path=str(output / f"demo-position-{pos}.png"))
                seq += 1
        page.wait_for_timeout(max(0, int((start + 90 - time.monotonic()) * 1000)))
        ctx.close()
        raw = video.path()
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-sseof",
                "-90",
                "-i",
                str(raw),
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(output / "demonstration.mp4"),
            ],
            check=True,
        )
        browser.close()
    (output / "demo-timing.json").write_text(
        json.dumps(
            dict(
                frames=len(measures),
                capture_to_ui_verified_ms=dict(
                    zip(
                        ["median", "p95", "max"], np.percentile(measures, [50, 95, 100])
                    )
                ),
                resume_to_ui_verified_ms=recovery_ms,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    run(args.headed, args.output)
