"""Characterise the saved CNN on simulated frames and on shifted real frames.

Writes evidence/interactive/model-behavior.json. The simulator's posture is
used only to score the CNN afterwards; the network sees just the grid.
"""

import json
from pathlib import Path

import numpy as np
import torch

from dataset import recording
from model import PostureCNN, inputs
from virtual_bed.body import Person
from virtual_bed.sensor import MAT_W, PX, MatPlacement, VirtualMat, clamp_person

OUT = Path("evidence/interactive/model-behavior.json")
WANT = {"back": "Supine", "right": "Right", "left": "Left"}
ROLL = {"back": 0.0, "right": 1.0, "left": -1.0}
NAMES = {"back": "On back", "right": "Right side", "left": "Left side"}


def main(model_path="model_v2.pt", out=OUT):
    torch.set_num_threads(1)
    ck = torch.load(model_path, map_location="cpu", weights_only=True)
    net = PostureCNN().eval()
    net.load_state_dict(ck["weights"])
    labels = ck["config"]["labels"]
    mat = MatPlacement()
    centre_x, hip_y = mat.x + MAT_W / 2, mat.y + 0.89

    def classify(grid):
        with torch.inference_mode():
            s = net(inputs(np.asarray(grid, float), 1000)).softmax(1)[0].numpy()
        return labels[int(s.argmax())], float(s.max())

    def case(posture, label, repeats=5, **kw):
        sensor = VirtualMat(seed=7)
        votes, coverage = [], None
        for i in range(repeats):
            p = Person(x=centre_x, y=hip_y, roll=ROLL[posture], breath=i * 1.3)
            for k, v in kw.items():
                setattr(p, k, v)
            clamp_person(p)
            grid, truth = sensor.read(p, mat)
            coverage = truth["coverage"]
            votes.append(classify(grid) if grid.max() else (None, None))
        pred = max(set(v[0] for v in votes), key=[v[0] for v in votes].count)
        score = float(np.mean([s for p_, s in votes if p_ == pred])) if pred else None
        return dict(
            label=label,
            posture=posture,
            prediction=pred,
            score=round(score, 3) if score else None,
            agreement=sum(v[0] == WANT[posture] for v in votes) / repeats,
            correct=pred == WANT[posture],
            coverage=coverage,
        )

    groups = []
    for posture in ("back", "left", "right"):
        cases = [
            case(posture, f"{dx * 100:+.0f} cm", x=centre_x + dx)
            for dx in (-0.3, -0.2, -0.1, -0.06, -0.03, 0, 0.03, 0.06, 0.1, 0.2, 0.3)
        ]
        groups.append(dict(title=f"{NAMES[posture]}: moved across the bed (+ is toward the bed's right side)", cases=cases))
    for posture in ("back", "left", "right"):
        cases = [case(posture, f"{dy * 100:+.0f} cm", y=hip_y + dy) for dy in (-0.1, -0.05, 0, 0.05, 0.1)]
        cases += [case(posture, f"turned {t:+d}°", theta=float(t)) for t in (-20, -10, -5, 5, 10, 20, 45, 90, 180)]
        groups.append(dict(title=f"{NAMES[posture]}: toward head (−) or foot (+), and turned", cases=cases))
    groups.append(
        dict(
            title="Rolling from back to right side (fraction of the roll completed)",
            cases=[
                case("right", f"roll {r:.1f}", roll=r)
                for r in (0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0)
            ],
        )
    )
    # Mid-roll there is no single true posture; score against the nearer one.
    for c in groups[-1]["cases"]:
        r = float(c["label"].split()[1])
        want = "Supine" if r < 0.5 else "Right"
        c["correct"] = c["prediction"] == want

    # Same question on real recordings: shift held-out frames across the mat.
    real = []
    for idx, name in enumerate(("back", "right", "left")):
        frames = np.concatenate([recording(s, idx + 1)[10::10] for s in (11, 12, 13)])
        for rows in (-8, -4, 0, 4, 8):
            shifted = np.zeros_like(frames)
            lo, hi = max(0, rows), 32 + min(0, rows)
            shifted[:, lo:hi] = frames[:, lo - rows : hi - rows]
            with torch.inference_mode():
                pred = net(inputs(shifted, 1000)).argmax(1).numpy()
            real.append(
                dict(
                    posture=name,
                    shift_rows=rows,
                    shift_cm=round(-rows * PX * 100, 1),
                    frames=len(frames),
                    accuracy=round(float((pred == idx).mean()), 3),
                )
            )
    groups.append(
        dict(
            title="Real held-out recordings (subjects 11–13) shifted sideways on the mat",
            cases=[
                dict(
                    label=f"{NAMES[r['posture']]} {r['shift_cm']:+.0f} cm",
                    prediction=WANT[r["posture"]] if r["accuracy"] >= 0.5 else None,
                    score=r["accuracy"],
                    correct=r["accuracy"] >= 0.9,
                )
                for r in real
            ],
        )
    )
    centred = [c for g in groups[:3] for c in g["cases"] if c["label"] == "+0 cm"]
    placements = [c for g in groups[:6] for c in g["cases"]]
    shifted = [r for r in real if r["shift_rows"] != 0]
    summary = (
        f"Model {ck['config']['version']}. Centred and aligned: "
        f"{', '.join(f'{NAMES[c['posture']]} → {NAMES.get({'Supine': 'back', 'Right': 'right', 'Left': 'left'}.get(c['prediction']), 'no load')} {c['score'] * 100:.0f}%' for c in centred)}. "
        f"Simulated placements correct: {sum(c['correct'] for c in placements)} of {len(placements)}. "
        f"Real held-out recordings moved 10–19 cm sideways: {min(r['accuracy'] for r in shifted) * 100:.0f}–"
        f"{max(r['accuracy'] for r in shifted) * 100:.0f}% of frames correct. "
        "Green matches the simulated posture (for real frames, at least 90% correct)."
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(model=ck["config"]["version"], summary=summary, groups=groups, real_shift=real), indent=1))
    print(summary)
    for g in groups:
        ok = sum(c["correct"] for c in g["cases"])
        print(f"{ok:2d}/{len(g['cases'])}  {g['title']}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="model_v2.pt")
    parser.add_argument("--out", type=Path, default=OUT)
    a = parser.parse_args()
    main(a.model, a.out)
