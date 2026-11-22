"""Fit the body model's bony prominences to real PmatData pressure statistics.

Targets come only from real recordings of training subjects 1-8 (medians per
posture), read as 0.1 mmHg per count. The CNN is not used here.
"""

import itertools
import json
from pathlib import Path

import numpy as np

import virtual_bed.body as body
from dataset import recording
from virtual_bed.sensor import MAT_W, MatPlacement, VirtualMat


def stats(frames_mmhg):
    f = np.asarray(frames_mmhg, float)
    return dict(
        peak=float(np.median(f.max((1, 2)))),
        p99=float(np.median(np.percentile(f.reshape(len(f), -1), 99, axis=1))),
        over100=float(np.median((f > 100).sum((1, 2)))),
        over40=float(np.median((f > 40).sum((1, 2)))),
        over10=float(np.median((f > 10).sum((1, 2)))),
    )


def target(position):
    real = np.concatenate([recording(s, position)[10:] for s in range(1, 9)])
    return stats(real / 10)


def simulate(roll):
    m = MatPlacement()
    sensor = VirtualMat(seed=1)
    p = body.Person(x=m.x + MAT_W / 2, y=m.y + 0.89, roll=roll)
    return stats(np.stack([sensor.read(p, m, noise=False)[0] / 10]))


def loss(s, t):
    return (
        abs(np.log(s["peak"] / t["peak"]))
        + abs(s["over100"] - t["over100"]) / 5
        + abs(s["over40"] - t["over40"]) / max(10, t["over40"])
        + abs(s["over10"] - t["over10"]) / t["over10"]
        + abs(s["p99"] - t["p99"]) / t["p99"]
    )


def set_row(rows, name, rho=None, share=None):
    for i, r in enumerate(rows):
        if r[0] == name:
            rows[i] = (r[0], r[1], r[2], rho or r[3], r[4] if rho is None else min(r[4], max(rho, 0.02)), share or r[5])


def rebuild(supine_rows, side_rows):
    body.SUPINE_T = body._table(supine_rows)
    body.RIGHT_T = body._table(side_rows)
    body.LEFT_T = body.RIGHT_T * np.array([-1, 1, -1, 1, 1, 1, 1])
    body.TABLES.update(back=body.SUPINE_T, right=body.RIGHT_T, left=body.LEFT_T)
    body.SINKS.update(
        back=body._solve_sinks(body.SUPINE_T),
        right=body._solve_sinks(body.RIGHT_T),
        left=body._solve_sinks(body.LEFT_T),
    )


def main():
    t_back, t_side = target(1), target(2)
    print("targets back", t_back, "\n        side", t_side)
    best_side, best_back = None, None
    for troch_rho, troch_share, shoulder_rho in itertools.product((0.035, 0.022, 0.014, 0.009), (0.09, 0.12, 0.15), (0.05, 0.035)):
        side = list(body.RIGHT_SIDE)
        set_row(side, "greater trochanter", troch_rho, troch_share)
        set_row(side, "shoulder", shoulder_rho)
        rebuild(body.SUPINE, side)
        s = simulate(1.0)
        score = loss(s, t_side)
        if best_side is None or score < best_side[0]:
            best_side = (score, dict(troch_rho=troch_rho, troch_share=troch_share, shoulder_rho=shoulder_rho), s)
    for pelvis_rho, thorax_rho, sacrum_rho, scap_share in itertools.product((0.2, 0.3, 0.45), (0.22, 0.32, 0.45), (0.05, 0.035), (0.04, 0.025)):
        sup = list(body.SUPINE)
        set_row(sup, "pelvis", pelvis_rho)
        set_row(sup, "thorax", thorax_rho)
        set_row(sup, "sacrum", sacrum_rho)
        set_row(sup, "scapula L", share=scap_share)
        set_row(sup, "scapula R", share=scap_share)
        rebuild(sup, body.RIGHT_SIDE)
        s = simulate(0.0)
        score = loss(s, t_back)
        if best_back is None or score < best_back[0]:
            best_back = (score, dict(pelvis_rho=pelvis_rho, thorax_rho=thorax_rho, sacrum_rho=sacrum_rho, scapula_share=scap_share), s)
    out = dict(
        targets=dict(back=t_back, side=t_side),
        side=dict(loss=best_side[0], params=best_side[1], simulated=best_side[2]),
        back=dict(loss=best_back[0], params=best_back[1], simulated=best_back[2]),
    )
    Path("evidence/model_v2").mkdir(parents=True, exist_ok=True)
    Path("evidence/model_v2/body-calibration.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("side", "back")}, indent=1))


if __name__ == "__main__":
    main()
