"""Exercise the exported React Native web UI against running local emulators and API."""

import json
import os
import time

import numpy as np
from playwright.sync_api import expect, sync_playwright

from dataset import recording
from replay import frame, post
from store import database

if os.getenv("TEXTILE_PROJECT", "demo-textilesense") != "demo-textilesense":
    raise RuntimeError("This test writes only to the local demo emulator")


def run():
    db = database()
    ref = db.document("sessions/demo/state/latest")
    previous = ref.get().to_dict() or {}
    start = previous.get("seq", -1) + 1
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path="/usr/bin/chromium", args=["--no-sandbox"]
        )
        context = browser.new_context(viewport={"width": 430, "height": 932})
        page = context.new_page()
        page.goto("http://127.0.0.1:8765")
        page.get_by_label("Password").fill(os.environ["DEMO_PASSWORD"])
        page.get_by_text("Sign in", exact=True).click()
        expect(page.get_by_text("Live monitoring")).to_be_visible()
        started = time.monotonic()
        for i in range(36):
            if i == 12:
                expect(page.get_by_text("Stale  ·", exact=False)).to_be_visible(
                    timeout=8000
                )
            p = 1 + i // 12
            seq = start + i
            payload = frame(
                recording(11, p)[35 + i % 12], seq, 11, p, 35 + i % 12, "demo"
            )
            begin = time.monotonic()
            res = post(payload)
            expect(page.get_by_text(res["frame_id"], exact=True)).to_be_visible(
                timeout=5000
            )
            ui_ms = (time.monotonic() - begin) * 1000
            snap = ref.get().to_dict()
            assert (
                snap["values"] == payload["values"]
                and snap["prediction"] == snap["labels"][int(np.argmax(snap["scores"]))]
            )
            expect(
                page.get_by_text("ESTIMATED POSTURE", exact=True).locator(
                    "xpath=following-sibling::*[1]"
                )
            ).to_have_text(snap["prediction"])
            paths = page.locator("svg path").evaluate_all(
                '(els)=>els.map(e=>[e.getAttribute("fill"),e.getAttribute("d")])'
            )
            colors = [
                "#142a3a",
                "#17435a",
                "#17647a",
                "#168d95",
                "#40b6ac",
                "#96d59c",
                "#eed97d",
                "#ffac62",
                "#fa7556",
            ]
            expected = {color: "" for color in colors}
            import math

            for j, v in enumerate(payload["values"]):
                color = colors[min(8, math.floor(math.log1p(v) / math.log(501) * 9))]
                expected[color] += f"M{j // 64} {j % 64}h1v1h-1z"
            assert dict(paths) == {k: v for k, v in expected.items() if v}
            if i == 12:
                assert snap["resumed"]
            if i in (5, 18):
                page.screenshot(path=f"evidence/live-{p}.png", full_page=True)
            results.append([res["latency_ms"], ui_ms])
            time.sleep(max(0, 1 - (time.monotonic() - begin)))
        elapsed = time.monotonic() - started
        assert post(payload)["status"] == "duplicates"
        future = dict(payload, seq=seq + 2, captured_ms=int(time.time() * 1000) - 4000)
        assert post(future)["status"] == "accepted"
        assert post(dict(future, seq=seq + 1))["status"] == "out_of_order"
        final = ref.get().to_dict()
        assert final["delayed"] and final["missing"] >= 1 and final["seq"] == seq + 2
        assert len(list(db.collection("sessions/demo/events").stream())) == 32
        page.get_by_text("History", exact=True).click()
        expect(page.get_by_text("Resumed ·", exact=False).first).to_be_visible()
        page.get_by_text("#" + str(seq + 2) + " ·", exact=False).click()
        expect(page.get_by_text(f"demo/{seq + 2} ·", exact=False)).to_be_visible()
        page.screenshot(path="evidence/history.png", full_page=True)
        page.get_by_text("Diagnostics", exact=True).click()
        expect(page.get_by_text("Last sequence")).to_be_visible()
        page.screenshot(path="evidence/diagnostics.png", full_page=True)
        context.set_offline(True)
        expect(page.get_by_text("Disconnected  ·", exact=False)).to_be_visible(
            timeout=35000
        )
        context.set_offline(False)
        expect(page.get_by_text("Connected", exact=True)).to_be_visible(timeout=20000)
        print(
            json.dumps(
                dict(
                    frames=36,
                    elapsed_s=elapsed,
                    rate_with_pause=36 / elapsed,
                    backend_ms_p50_p95=np.percentile(results, [50, 95], axis=0)[
                        :, 0
                    ].tolist(),
                    browser_observed_ms_p50_p95=np.percentile(
                        results, [50, 95], axis=0
                    )[:, 1].tolist(),
                    duplicates=final["duplicates"],
                    missing=final["missing"],
                    out_of_order=final["out_of_order"],
                    history=32,
                    disconnect_reconnect=True,
                ),
                indent=2,
            )
        )


if __name__ == "__main__":
    run()
