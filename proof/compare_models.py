"""Compare CNN v1 and v2 on unseen real people, moved and turned.

Test subjects 11-13 were never used for training or model selection by
either version. Placements are produced with the same physical-space
transform used for v2's training augmentation, at fixed values (not random).
Writes evidence/model_v2/comparison.json.
"""

import json
from pathlib import Path

import torch

from model import PostureCNN
from train import SPLITS, load
from train_v2 import place

OUT = Path("evidence/model_v2/comparison.json")
CASES = [
    ("as recorded", 0, 0, 0),
    ("4 rows (10 cm) across", 0, 4, 0),
    ("-4 rows (10 cm) across", 0, -4, 0),
    ("8 rows (19 cm) across", 0, 8, 0),
    ("-8 rows (19 cm) across", 0, -8, 0),
    ("4 columns (12 cm) toward feet", 0, 0, 4),
    ("-4 columns (12 cm) toward head", 0, 0, -4),
    ("turned 10°", 10, 0, 0),
    ("turned -10°", -10, 0, 0),
    ("turned 20°", 20, 0, 0),
    ("turned -20°", -20, 0, 0),
    ("head to foot (180°)", 180, 0, 0),
    ("turned 15° and moved 6 rows", 15, 6, 0),
]


def model(path):
    ck = torch.load(path, map_location="cpu", weights_only=True)
    net = PostureCNN().eval()
    net.load_state_dict(ck["weights"])
    return net, ck["config"]["version"]


def main():
    torch.set_num_threads(2)
    z, t, _ = load(SPLITS["test"])
    nets = [model("model.pt"), model("model_v2.pt")]
    rows = []
    for name, angle, dr, dc in CASES:
        n = len(z)
        moved = place(z, [angle] * n, [dr] * n, [dc] * n)
        row = dict(case=name, frames=n)
        for net, version in nets:
            with torch.no_grad():
                row[version] = round(float((net(moved).argmax(1) == t).float().mean()), 4)
        rows.append(row)
        print(f"{name:32s} " + "  ".join(f"{v}: {row[v] * 100:5.1f}%" for _, v in nets))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(dict(test_subjects=SPLITS["test"], results=rows), indent=1))


if __name__ == "__main__":
    main()
