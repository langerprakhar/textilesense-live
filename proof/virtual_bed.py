"""Control the virtual mat and verify the real Firestore and Expo observations."""

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np
import torch
from playwright.sync_api import expect, sync_playwright

from model import PostureCNN, inputs
from store import database

OUT = Path("evidence/virtual_bed")


def run():
    if (
        os.getenv("TEXTILE_PROJECT") != "demo-textilesense-bed"
        or os.getenv("TEXTILE_EMULATOR_PORT") != "8180"
    ):
        raise RuntimeError("Use the phase-two emulator")
    torch.set_num_threads(1)
    checkpoint = torch.load("model.pt", map_location="cpu", weights_only=True)
    model = PostureCNN().eval()
    model.load_state_dict(checkpoint["weights"])
    cfg = checkpoint["config"]
    ref = database().document("sessions/virtual-bed/state/latest")
    evidence = []
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=shutil.which("chromium"))
        size = {"width": 1250, "height": 960}
        ctx = b.new_context(viewport=size, record_video_dir=tmp, record_video_size=size)
        page = ctx.new_page()
        page.goto("http://127.0.0.1:8775")
        app = page.frame_locator("iframe")
        app.get_by_label("Password").fill(os.environ["DEMO_PASSWORD"])
        app.get_by_text("Sign in", exact=True).click()
        expect(app.get_by_text("Live monitoring", exact=True)).to_be_visible()
        started = time.monotonic()
        page.get_by_text("Inspect one sensor cell").click()
        for pose, button in [
            ("empty", "Get up"),
            ("back", "Lie on back"),
            ("left", "Turn left"),
            ("right", "Turn right"),
            ("empty", "Get up"),
        ]:
            page.get_by_role("button", name=button, exact=True).click()
            if not evidence:
                page.get_by_role("button", name="Start sensor").click()
            page.wait_for_timeout(6100)
            s = ref.get().to_dict()
            assert (
                s["source"] == "virtual_pressure_mat"
                and s["scenario"] == pose
                and len(s["values"]) == 2048
            )
            assert s["device"] == "virtual-mat-01" and "recording" not in s
            if pose == "empty":
                assert (
                    max(s["values"]) == 0
                    and s["scores"] == []
                    and s["prediction"] == "Empty bed"
                )
            else:
                with torch.inference_mode():
                    calculated = (
                        model(inputs(np.array(s["values"]), cfg["cap"]))
                        .softmax(1)[0]
                        .tolist()
                    )
                np.testing.assert_allclose(s["scores"], calculated, rtol=1e-5)
                assert s["prediction"] == cfg["labels"][np.argmax(calculated)]
            expect(app.get_by_text(s["frame_id"], exact=True)).to_be_visible(
                timeout=1500
            )
            expect(
                app.get_by_text("ESTIMATED POSTURE", exact=True).locator(
                    "xpath=following-sibling::*[1]"
                )
            ).to_have_text(s["prediction"])
            evidence.append(
                {
                    k: s[k]
                    for k in (
                        "frame_id",
                        "source",
                        "scenario",
                        "prediction",
                        "scores",
                        "captured_ms",
                        "digest",
                    )
                }
                | {
                    "peak": max(s["values"]),
                    "cells": len(s["values"]),
                    "cell_15_34": s["values"][15 * 64 + 34],
                }
            )
            if pose == "left":
                page.screenshot(path=str(OUT / "virtual-bed.png"))
        page.get_by_role("button", name="Pause sensor").click()
        expect(
            app.get_by_text("Stale · Virtual pressure mat", exact=True)
        ).to_be_visible(timeout=6000)
        stopped = ref.get().get("seq")
        page.wait_for_timeout(1200)
        assert ref.get().get("seq") == stopped
        page.get_by_role("button", name="Lie on back").click()
        page.get_by_role("button", name="Start sensor").click()
        expect(
            app.get_by_text("Live · Virtual pressure mat", exact=True)
        ).to_be_visible()
        page.wait_for_timeout(2500)
        page.get_by_role("button", name="Pause sensor").click()
        page.wait_for_timeout(1000)
        s = ref.get().to_dict()
        assert s["seq"] > stopped and s["scenario"] == "back"
        expect(app.get_by_text(s["frame_id"], exact=True)).to_be_visible()
        panel_doc = page.request.get("http://127.0.0.1:8775/reading").json()["document"]
        assert panel_doc == s
        expect(page.locator("#cell")).to_contain_text(
            str(s["values"][15 * 64 + 34]) + " simulated counts"
        )
        assert len(list(ref.parent.parent.collection("events").stream())) <= 32
        url = page.get_by_role("link", name="Open Firestore database").get_attribute(
            "href"
        )
        page.goto("http://127.0.0.1:8775" + url)
        expect(page.get_by_text('"' + s["frame_id"] + '"', exact=True)).to_be_visible(
            timeout=20000
        )
        page.screenshot(path=str(OUT / "firestore.png"))
        page.wait_for_timeout(3000)
        elapsed = time.monotonic() - started
        video = page.video
        ctx.close()
        subprocess.run(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                "-sseof",
                str(-elapsed),
                "-i",
                str(video.path()),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(OUT / "virtual-bed.mp4"),
            ],
            check=True,
        )
        b.close()
    (OUT / "observed.json").write_text(
        json.dumps(
            {
                "actions": evidence,
                "pause_and_resume": True,
                "firestore_ui_frame": s["frame_id"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    run()
