"""Operate the interactive bed like a person and verify every hop.

Needs the local virtual bed running (scripts\\virtual-bed.cmd) and its viewer
password in DEMO_PASSWORD. Uses the installed Microsoft Edge (or Chromium).
Writes evidence/interactive/acceptance.json, screenshots and a video.

Checks, kept separate:
  simulator  - what the virtual mat measured matches what was done to it
  model      - the CNN's output, recorded next to the operator's setting
  transport  - sequence, Firestore documents, pause, outage and recovery,
               and the frame the phone stand-in reports drawing
"""

import json
import os
import shutil
import time
from pathlib import Path

import numpy as np
from playwright.sync_api import sync_playwright

from store import database

OUT = Path("evidence/interactive")
URL = "http://127.0.0.1:8775"
ORIGIN = {"Origin": URL}


def run():
    assert os.getenv("TEXTILE_PROJECT") == "demo-textilesense-bed", "use the local virtual bed"
    db = database()
    latest = db.document("sessions/virtual-bed/state/latest")
    viewers = db.collection("sessions/virtual-bed/viewers")
    OUT.mkdir(parents=True, exist_ok=True)
    log = dict(simulator=[], model=[], transport=[])

    def doc():
        return latest.get().to_dict() or {}

    def wait_frames(n=2, timeout=12):
        start = doc().get("seq", -1)
        end = time.time() + timeout
        while time.time() < end:
            d = doc()
            if d.get("seq", -1) >= start + n:
                return d
            time.sleep(0.25)
        raise AssertionError(f"fewer than {n} new frames in {timeout}s")

    def record(kind, step, ok, **facts):
        log[kind].append(dict(step=step, ok=bool(ok), **facts))
        print(f"[{'PASS' if ok else 'FAIL'}] {kind:9s} {step}: {facts}")
        return ok

    browser_kw = {}
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(channel="msedge", **browser_kw)
        except Exception:
            browser = pw.chromium.launch(**browser_kw)
        video_dir = OUT / "video-tmp"
        console_ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir=str(video_dir),
            record_video_size={"width": 1440, "height": 900},
        )
        page = console_ctx.new_page()
        phone_ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        phone = phone_ctx.new_page()

        def api(op, **kw):
            r = page.request.post(URL + "/api/scene", data=dict(op=op, **kw), headers=ORIGIN)
            assert r.ok, r.text()
            return r.json()

        def tx(action):
            assert page.request.post(URL + "/api/transmit", data={"action": action}, headers=ORIGIN).ok

        def centre_of(sel):
            b = page.locator(sel).first.bounding_box()
            return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2

        def drag(start, end, steps=25, pause=25):
            page.mouse.move(*start)
            page.mouse.down()
            for i in range(1, steps + 1):
                page.mouse.move(start[0] + (end[0] - start[0]) * i / steps, start[1] + (end[1] - start[1]) * i / steps)
                page.wait_for_timeout(pause)
            page.mouse.up()

        def cm_to_px():
            return page.evaluate("document.getElementById('bed').getScreenCTM().a")

        # Clean slate, then the phone stand-in signs in.
        tx("pause")
        tx("restore_link")
        api("get_up")
        api("remove_mat")
        page.goto(URL)
        phone.goto(URL + "/monitor")
        phone.get_by_label("Password").fill(os.environ["DEMO_PASSWORD"])
        phone.get_by_role("button", name="Sign in").click()
        page.wait_for_timeout(1200)
        page.screenshot(path=OUT / "01-empty-bed.png")

        # 1. Drag the mat from the toolbox onto the bed.
        bed = page.locator("#bed").bounding_box()
        drag(centre_of("#toolMat"), (bed["x"] + bed["width"] * 0.5, bed["y"] + bed["height"] * 0.52))
        page.wait_for_timeout(500)
        scene = page.request.get(URL + "/api/live").json()["scene"]
        record("simulator", "mat dragged onto bed", scene["mat"] is not None, mat=scene["mat"])

        # 2. Transmit with nobody on the mat: empty readings.
        page.get_by_role("button", name="Start transmitting").click()
        d = wait_frames(2)
        record("simulator", "empty mat reads zero", max(d["values"]) == 0, frame=d["frame_id"])
        record("model", "empty mat is not classified", d["prediction"] is None and d["model_status"] == "not_run_no_load", frame=d["frame_id"])
        page.screenshot(path=OUT / "02-mat-placed.png")

        # 3. Drag the person from the toolbox onto the mat.
        mat_box = page.locator("#matG").bounding_box()
        drop = (mat_box["x"] + mat_box["width"] / 2, mat_box["y"] + mat_box["height"] * 0.48)
        drag(centre_of("#toolPerson"), drop)
        page.wait_for_timeout(300)
        page.get_by_role("button", name="Centre on mat").click()
        d = wait_frames(3)
        m = d["measurement"]
        record("simulator", "person on mat loads it", abs(m["load_kg"] - 75) < 4 and d["simulator"]["coverage"] > 0.97,
               frame=d["frame_id"], load_kg=m["load_kg"], coverage=d["simulator"]["coverage"])
        record("model", "on back, centred", True, frame=d["frame_id"], selected="back", cnn=d["prediction"],
               scores=[round(s, 3) for s in d["scores"]], matches=d["prediction"] == "Supine")
        page.screenshot(path=OUT / "03-person-on-back.png")

        # 4. Drag the body continuously across the bed and back; frames follow.
        px = cm_to_px()
        hip = centre_of("#personG circle")
        rows = []
        for k in range(1, 6):
            target = (hip[0] - 4 * px * k, hip[1])
            drag((hip[0] - 4 * px * (k - 1), hip[1]), target, steps=8, pause=40)
            d = wait_frames(1)
            rows.append((d["seq"], d["measurement"]["centroid_row"], d["simulator"]["x_m"]))
        record("simulator", "dragging left raises the centroid row continuously",
               all(b[1] > a[1] for a, b in zip(rows, rows[1:])), samples=rows)
        page.screenshot(path=OUT / "04-moved-left.png")
        hip = centre_of("#personG circle")
        drag(hip, (hip[0], hip[1] - 8 * px), steps=10, pause=40)
        d1 = wait_frames(2)
        hip = centre_of("#personG circle")
        drag(hip, (hip[0], hip[1] + 16 * px), steps=16, pause=40)
        d2 = wait_frames(2)
        record("simulator", "toward the foot moves the centroid to higher columns",
               d2["measurement"]["centroid_col"] > d1["measurement"]["centroid_col"] + 3,
               head_col=d1["measurement"]["centroid_col"], foot_col=d2["measurement"]["centroid_col"])
        d = doc()
        record("model", "after moving (outside training placement)", True, frame=d["frame_id"],
               cnn=d["prediction"], flags=d.get("input_flags"), coverage=d["simulator"]["coverage"])

        # 5. Partly off the mat: the uncovered part is not measured.
        page.get_by_role("button", name="Centre on mat").click()
        hip = centre_of("#personG circle")
        drag(hip, (hip[0] - 22 * px, hip[1]), steps=20, pause=30)
        d = wait_frames(2)
        record("simulator", "body partly off the mat", 0.15 < d["simulator"]["coverage"] < 0.95 and abs(d["measurement"]["load_n"] - d["simulator"]["mat_force_n"]) < 0.06 * d["simulator"]["mat_force_n"] + 8,
               coverage=d["simulator"]["coverage"], measured_n=d["measurement"]["load_n"], truth_n=d["simulator"]["mat_force_n"])
        record("model", "partly off the mat", True, frame=d["frame_id"], cnn=d["prediction"], flags=d.get("input_flags"))
        page.screenshot(path=OUT / "05-partly-off-mat.png")

        # 6. Turn, then roll; rolling is a separate action from moving.
        page.get_by_role("button", name="Centre on mat").click()
        page.locator("#turn").fill("20")
        d = wait_frames(2)
        record("simulator", "turned 20 degrees", abs(d["simulator"]["theta_deg"] - 20) < 1, theta=d["simulator"]["theta_deg"])
        record("model", "turned 20 degrees on back", True, frame=d["frame_id"], cnn=d["prediction"])
        page.screenshot(path=OUT / "06-turned.png")
        page.get_by_role("button", name="Centre on mat").click()
        for button, posture, want in (("Right side", "right", "Right"), ("Left side", "left", "Left"), ("On back", "back", "Supine")):
            before = api("posture", posture=posture)["person"]
            page.get_by_role("button", name=button, exact=True).click()
            page.wait_for_timeout(3000)  # a full side-to-side roll takes 2.8 s
            d = wait_frames(2)
            same_place = abs(d["simulator"]["x_m"] - before["x"]) < 1e-6 and abs(d["simulator"]["y_m"] - before["y"]) < 1e-6
            record("simulator", f"roll to {posture} keeps position", same_place and d["simulator"]["roll"] == {"right": 1, "left": -1, "back": 0}[posture],
                   roll=d["simulator"]["roll"])
            record("model", f"rolled to {posture}", True, frame=d["frame_id"], selected=posture, cnn=d["prediction"],
                   top_score=round(max(d["scores"]), 3), matches=d["prediction"] == want)
            page.screenshot(path=OUT / f"07-{posture}.png")

        # 7. Get up: empty readings keep arriving.
        page.get_by_role("button", name="Get up").click()
        d = wait_frames(2)
        record("simulator", "get up empties the mat", max(d["values"]) == 0 and not d["simulator"]["person_on_bed"], frame=d["frame_id"])
        record("model", "empty after getting up", d["prediction"] is None, frame=d["frame_id"])
        page.screenshot(path=OUT / "08-got-up.png")

        # Put the person back for the transport checks.
        api("place_person", x=0.76, y=0.98)
        api("centre")
        wait_frames(2)

        # 8. Phone stand-in draws the same frame and says so.
        phone.wait_for_timeout(1500)
        d = doc()
        shown = phone.get_by_text(d["frame_id"], exact=True).count() > 0 or phone.get_by_text(f"virtual-bed/{d['seq'] - 1}", exact=True).count() > 0
        receipt = [r.to_dict() for r in viewers.stream()]
        rec = max(receipt, key=lambda r: r["seq"]) if receipt else {}
        record("transport", "phone stand-in shows the committed frame and reports it", shown and d["seq"] - rec.get("seq", -99) <= 1,
               committed=d["frame_id"], receipt=rec.get("frame_id"), physical=rec.get("physical_device"), platform=rec.get("platform"))
        phone.screenshot(path=OUT / "09-phone-standin-live.png")

        # 9. Pause: no new frames, phone marks the reading stale.
        page.get_by_role("button", name="Pause transmission").click()
        page.wait_for_timeout(1500)  # a frame already in flight may still commit
        paused_at = doc()["seq"]
        missing_before = doc()["missing"]
        page.wait_for_timeout(4500)
        stale = phone.get_by_text("Stale", exact=True).count() > 0
        record("transport", "pause stops frames and the phone shows Stale", doc()["seq"] == paused_at and stale, seq=paused_at)
        phone.screenshot(path=OUT / "10-phone-stale.png")
        page.screenshot(path=OUT / "10-paused.png")

        # 10. Resume: the next number follows on, no gap is invented.
        page.get_by_role("button", name="Start transmitting").click()
        d = wait_frames(2)
        record("transport", "resume continues the sequence", d["validation"]["sequence"] == "next" and d["missing"] == missing_before and d["resumed"] is False,
               seq=d["seq"], sequence=d["validation"]["sequence"], missing=d["missing"])
        first_after = db.document(f"sessions/virtual-bed/events/{(d['count'] - 2) % 32}").get().to_dict()
        record("transport", "first frame after the pause is flagged as resumed", first_after.get("resumed") is True, frame=first_after.get("frame_id"))

        # 11. Link outage and recovery: frames are lost, Python counts them.
        earlier = set(page.request.get(URL + "/api/diagnostics").json()["dropped"])
        tx("drop_link")
        page.wait_for_timeout(3300)
        lost = sorted(set(page.request.get(URL + "/api/diagnostics").json()["dropped"]) - earlier)
        tx("restore_link")
        d = wait_frames(1)
        record("transport", "outage gap detected after recovery", d["validation"]["sequence"].startswith("gap") and d["gap_frames"] == len(lost),
               lost=lost, sequence=d["validation"]["sequence"], missing=d["missing"])
        page.goto(URL + "/diagnostics")
        page.wait_for_timeout(1500)
        page.screenshot(path=OUT / "11-diagnostics.png", full_page=True)
        page.goto(URL)
        page.wait_for_timeout(1500)
        page.screenshot(path=OUT / "12-recovered.png")

        # 12. Every committed frame's map matches its own stored prediction.
        events = [e.to_dict() for e in db.collection("sessions/virtual-bed/events").stream()]
        import torch

        from model import PostureCNN, inputs

        ck = torch.load("model.pt", map_location="cpu", weights_only=True)
        net = PostureCNN().eval()
        net.load_state_dict(ck["weights"])
        mismatched = []
        for e in events:
            if not e.get("scores"):
                continue
            with torch.inference_mode():
                s = net(inputs(np.array(e["values"]), 1000)).softmax(1)[0].numpy()
            if not np.allclose(s, e["scores"], atol=1e-5):
                mismatched.append(e["frame_id"])
        record("transport", "stored scores recompute from the stored grid", not mismatched, checked=len(events), mismatched=mismatched)

        tx("pause")
        console_ctx.close()
        phone_ctx.close()
        browser.close()
    videos = sorted(video_dir.glob("*.webm"))
    if videos:
        shutil.move(str(videos[-1]), OUT / "acceptance-console.webm")
    shutil.rmtree(video_dir, ignore_errors=True)
    summary = {k: f"{sum(c['ok'] for c in v)}/{len(v)}" for k, v in log.items()}
    (OUT / "acceptance.json").write_text(json.dumps(dict(summary=summary, **log), indent=1))
    print("summary", summary)
    failed = [c for v in log.values() for c in v if not c["ok"]]
    if failed:
        raise SystemExit(f"{len(failed)} check(s) failed")


if __name__ == "__main__":
    run()
