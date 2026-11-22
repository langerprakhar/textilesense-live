"""Train PostureCNN v2: same data, splits and network, plus placement augmentation.

v1 (train.py) learned only from people lying where the PmatData participants
lay, so a body shifted about 10 cm or turned 10-20 degrees could change its
answer. v2 sees the same real recordings, randomly moved and turned while
training, so posture is learned apart from placement.

Augmentations, applied fresh to every training batch (never to test data):
  * shift: up to +/-10 sensor rows (24 cm) across and +/-6 columns (17 cm) along
  * turn: uniform +/-25 degrees about the mat centre, in physical space (the
    sensels are 2.4 x 2.9 cm, so pixel-space rotation would distort the body)
  * head-to-foot: 180-degree turn with probability 0.25 (label unchanged)
  * no left/right mirroring. A variant that also mirrored frames (swapping the
    Right and Left labels) scored lower on validation subjects 9-10, likely
    because people do not lie exactly mirror-symmetrically; --mirror rebuilds it.
Readings that move off the mat are lost, as they would be on a real mat.

No simulator frames are used for training, so the virtual bed remains an
independent test. Model selection uses validation subjects 9-10 only:
the mean of macro-F1 on their unaltered frames and on a fixed augmented copy.
Test subjects 11-13 are touched once, after selection.
"""

import copy
import json
import math
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import f1_score

from dataset import LABELS
from model import PostureCNN
from train import SPLITS, load, metrics

OUT = Path("model_v2.pt")
EVIDENCE = Path("evidence/model_v2")
HALF = torch.tensor([64 * 2.9 / 2, 32 * 2.4 / 2])  # physical half-length (x: columns) and half-width (y: rows), cm
SWAP = torch.tensor([0, 2, 1])  # Supine stays, Right <-> Left


def place(x, angle_deg, shift_rows, shift_cols, mirror=None):
    """Move and turn frames (N,1,32,64) in physical space; zero fills the gaps."""
    n = x.shape[0]
    a = torch.as_tensor(angle_deg, dtype=torch.float32).reshape(n) * math.pi / 180
    cos, sin = torch.cos(a), torch.sin(a)
    rot = torch.stack([torch.stack([cos, -sin], -1), torch.stack([sin, cos], -1)], -2)
    s = torch.diag(HALF)
    s_inv = torch.diag(1 / HALF)
    theta = torch.zeros(n, 2, 3)
    theta[:, :, :2] = s_inv @ rot @ s
    # affine_grid maps output to input coordinates, so shift by the negative
    theta[:, 0, 2] = -torch.as_tensor(shift_cols, dtype=torch.float32).reshape(n) * 2 / 64
    theta[:, 1, 2] = -torch.as_tensor(shift_rows, dtype=torch.float32).reshape(n) * 2 / 32
    grid = F.affine_grid(theta, list(x.shape), align_corners=False)
    out = F.grid_sample(x, grid, mode="bilinear", padding_mode="zeros", align_corners=False)
    if mirror is not None:
        out = torch.where(mirror.reshape(n, 1, 1, 1), out.flip(2), out)
    return out


MIRROR_P = 0.0  # the mirror variant (0.5) lost on validation subjects; see --mirror


def augment(x, y, gen):
    n = x.shape[0]
    angle = (torch.rand(n, generator=gen) * 2 - 1) * 25
    angle = angle + 180 * (torch.rand(n, generator=gen) < 0.25)
    rows = (torch.rand(n, generator=gen) * 2 - 1) * 10
    cols = (torch.rand(n, generator=gen) * 2 - 1) * 6
    mirror = torch.rand(n, generator=gen) < MIRROR_P
    out = place(x, angle, rows, cols, mirror)
    return out, torch.where(mirror, SWAP[y], y)


def main(out=OUT, version="pmat-flat-v2", evidence=EVIDENCE / "train.json"):
    torch.manual_seed(41)
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    gen = torch.Generator().manual_seed(41)
    x, y, _ = load(SPLITS["train"])
    v, w, _ = load(SPLITS["validation"])
    v_aug, w_aug = augment(v, w, torch.Generator().manual_seed(7))  # fixed for fair selection
    net = PostureCNN()
    optim = torch.optim.Adam(net.parameters(), lr=0.002)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(optim, T_max=40)
    history, best = [], -1
    for epoch in range(40):
        net.train()
        for batch in torch.randperm(len(x), generator=gen).split(64):
            xb, yb = augment(x[batch], y[batch], gen)
            optim.zero_grad()
            loss = F.cross_entropy(net(xb), yb)
            loss.backward()
            optim.step()
        sched.step()
        net.eval()
        with torch.no_grad():
            plain = f1_score(w, net(v).argmax(1), average="macro")
            moved = f1_score(w_aug, net(v_aug).argmax(1), average="macro")
        score = (plain + moved) / 2
        history.append(dict(epoch=epoch + 1, plain=round(plain, 4), augmented=round(moved, 4)))
        print(f"epoch {epoch + 1:2d}  validation macro-F1 plain {plain:.3f}  moved/turned {moved:.3f}", flush=True)
        if score > best:
            best, weights, selected = score, copy.deepcopy(net.state_dict()), epoch + 1
    net.load_state_dict(weights)
    cfg = dict(
        version=version,
        architecture="PostureCNN",
        labels=LABELS,
        cap=1000,
        transform="log1p",
        splits=SPLITS,
        seed=41,
        epoch=selected,
        augmentation=dict(
            shift_rows=10, shift_cols=6, turn_deg=25, head_to_foot_p=0.25, mirror_p=MIRROR_P,
            space="physical, 2.4 x 2.9 cm sensels", simulator_frames_used=False,
        ),
    )
    torch.save(dict(config=cfg, weights=weights), out)
    z, t, subjects = load(SPLITS["test"])
    with torch.no_grad():
        p = net.eval()(z).argmax(1)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(dict(
        selection_score=round(best, 4),
        config=cfg,
        validation=history,
        test=metrics(t, p),
        by_subject={str(s): metrics(t[subjects == s], p[subjects == s]) for s in SPLITS["test"]},
    ), indent=1))
    print(f"selected epoch {selected}; held-out test accuracy {metrics(t, p)['accuracy']:.4f}")


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument("--mirror", action="store_true", help="also mirror left/right (the rejected variant)")
    a = parser.parse_args()
    if a.mirror:
        globals()["MIRROR_P"] = 0.5
        main(Path("model_v2_mirror.pt"), "pmat-flat-v2-mirror", EVIDENCE / "train-mirror.json")
    else:
        main()
