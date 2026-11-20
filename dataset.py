"""PmatData v1.0.0, Experiment I, standard flat-bed positions only."""

import hashlib
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path("data")
URL = "https://physionet.org/files/pmd/1.0.0/"
LABELS = ["Supine", "Right", "Left"]


def fetch(name):
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["curl", "--retry", "3", "-fsSL", URL + name, "-o", str(path)], check=True
    )
    return path


def recording(subject, position):
    path = ROOT / f"experiment-i/S{subject}/{position}.txt"
    values = np.loadtxt(path, dtype=np.float32, ndmin=2)
    if values.shape[1] != 2048 or not np.isfinite(values).all() or values.min() < 0:
        raise ValueError(path)
    # Each text row is a frame. Display as 64 sensor rows of width 32,
    # then transpose to the project's (width, length) model convention.
    return values.reshape(-1, 64, 32).transpose(0, 2, 1).copy()


if __name__ == "__main__":
    sums = dict(
        line.split()[::-1] for line in fetch("SHA256SUMS.txt").read_text().splitlines()
    )

    def download(name):
        path = fetch(name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != sums[name]:
            raise ValueError(f"Checksum mismatch: {name}")

    files = [f"experiment-i/S{s}/{p}.txt" for s in range(1, 14) for p in range(1, 4)]
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(download, files))
    print("Verified", len(files), "recordings")
