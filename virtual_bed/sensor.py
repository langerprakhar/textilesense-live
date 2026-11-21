"""Virtual 32 x 64 pressure mat lying on a queen bed.

Geometry (metres, bed frame from virtual_bed.body):
  * Bed: 1.52 m wide x 2.03 m long.
  * Mat sensing area: 32 rows across x 64 columns along the bed. Sensels are
    2.4 cm across and 2.9 cm along the bed, i.e. 0.768 m x 1.856 m. PmatData
    does not state the Vista FSA SoftFlex pitch; these values reproduce the
    proportions of an adult on the grid in those recordings (head near
    column 1, heels near column 62, shoulders about 20 rows wide). Column 0 is
    at the head end.
  * Row 0 lies along the mat's RIGHT edge as seen from above with the head at
    the top. In the PmatData recordings the CNN learned from, side-lying knees
    sit at higher row numbers for "Right" and lower ones for "Left", so the
    subject's right hand points toward row 31. Matching that orientation keeps
    simulated frames in the same coordinate convention as the training data.

Units: every value is simulated interface pressure in tenths of a millimetre of
mercury (0.1 mmHg per count). 1 mmHg = 133.322 Pa. Values below the 1.0 mmHg
dead band read 0, so an unloaded mat sends exact zeros.

Coverage: the mat measures only what presses on its sensing area. Load on the
bed outside the mat is real in the simulation but invisible to the sensor.
"""

from dataclasses import dataclass

import numpy as np

from virtual_bed.body import G, MMHG, Person

BED_W, BED_L = 1.52, 2.03
ROWS, COLS = 32, 64
PX, PY = 0.024, 0.029  # metres across and along the bed
CELL_AREA = PX * PY
MAT_W, MAT_L = ROWS * PX, COLS * PY
SUB = 3  # sub-samples per cell side when integrating pressure over a cell
SPREAD = 1.0  # cover-layer load spreading, Gaussian sigma in cells
DEADBAND_MMHG = 1.0
SATURATION = 4095  # counts; 409.5 mmHg
SCALE = 0.1  # mmHg per count
PAD = 4  # cells of margin computed around the mat so spreading at the edges is exact


def _kernel(sigma):
    r = int(np.ceil(3 * sigma))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    return k / k.sum()


KERNEL = _kernel(SPREAD)


def blur(field):
    out = np.apply_along_axis(np.convolve, 0, field, KERNEL, mode="same")
    return np.apply_along_axis(np.convolve, 1, out, KERNEL, mode="same")


@dataclass
class MatPlacement:
    x: float = (BED_W - MAT_W) / 2  # left edge of the sensing area
    y: float = (BED_L - MAT_L) / 2  # head edge of the sensing area

    def clamp(self):
        self.x = float(np.clip(self.x, 0, BED_W - MAT_W))
        self.y = float(np.clip(self.y, 0, BED_L - MAT_L))
        return self


def cell_centres(mat, pad=0):
    """Bed coordinates of each (row, col) cell centre, shape (32+2p, 64+2p)."""
    r = np.arange(-pad, ROWS + pad)
    c = np.arange(-pad, COLS + pad)
    x = mat.x + (ROWS - 1 - r + 0.5) * PX  # row 0 at the right edge
    y = mat.y + (c + 0.5) * PY
    return np.meshgrid(x, y, indexing="ij")


def true_cell_pressure(person, mat, pad=0):
    """Exact mean pressure (Pa) over each cell, before any sensor effects."""
    X, Y = cell_centres(mat, pad)
    offsets = (np.arange(SUB) + 0.5) / SUB - 0.5
    total = np.zeros(X.shape)
    for ox in offsets:
        for oy in offsets:
            total += person.pressure(X + ox * PX, Y + oy * PY)
    return total / SUB**2


class VirtualMat:
    """Turns ground-truth contact into sensor counts with simple sensor effects."""

    def __init__(self, seed=41):
        rng = np.random.default_rng(seed)
        self.gain = 1 + rng.normal(0, 0.03, (ROWS, COLS))  # fixed per-cell gain
        self.rng = np.random.default_rng(seed + 1)

    def read(self, person, mat, noise=True):
        """Return (counts int[32, 64], truth dict)."""
        if person is None:
            return np.zeros((ROWS, COLS), dtype=int), truth(None, mat, None)
        padded = true_cell_pressure(person, mat, PAD)
        spread = blur(padded)[PAD:-PAD, PAD:-PAD]
        mmhg = spread / MMHG
        if noise:
            mmhg = mmhg * self.gain * (1 + self.rng.normal(0, 0.015, mmhg.shape))
            mmhg = mmhg + self.rng.normal(0, 0.2, mmhg.shape) * (mmhg > 0.5)
        mmhg[mmhg < DEADBAND_MMHG] = 0
        counts = np.rint(mmhg / SCALE).clip(0, SATURATION).astype(int)
        # Coverage counts the load that reaches the sensing area after the
        # cover layer spreads it, which is what the sensors can respond to.
        return counts, truth(person, mat, spread)


def truth(person, mat, cell_pa):
    """Simulator ground truth for a reading. Diagnostic only; not a model input."""
    if person is None:
        return dict(on_bed=False, body_force_n=0.0, mat_force_n=0.0, coverage=None)
    body = person.mass * G
    on_mat = float(cell_pa.sum() * CELL_AREA)
    return dict(
        on_bed=True,
        body_force_n=round(body, 1),
        mat_force_n=round(on_mat, 1),
        coverage=round(min(1.0, on_mat / body), 4),
    )


def measure(counts):
    """Quantities derivable from the transmitted grid alone."""
    v = np.asarray(counts, dtype=float).reshape(ROWS, COLS) * SCALE
    loaded = v > 0
    n = int(loaded.sum())
    force = float(v.sum() * MMHG * CELL_AREA)
    out = dict(
        peak_mmhg=round(float(v.max()), 1),
        contact_cells=n,
        contact_area_m2=round(n * CELL_AREA, 4),
        mean_contact_mmhg=round(float(v[loaded].mean()), 1) if n else 0.0,
        load_n=round(force, 1),
        load_kg=round(force / G, 1),
        saturated_cells=int((np.asarray(counts) >= SATURATION).sum()),
    )
    if n:
        rr, cc = np.indices(v.shape)
        out["centroid_row"] = round(float((v * rr).sum() / v.sum()), 2)
        out["centroid_col"] = round(float((v * cc).sum() / v.sum()), 2)
        edge = v.copy()
        edge[1:-1, 1:-1] = 0
        out["edge_load_fraction"] = round(float(edge.sum() / v.sum()), 4)
    else:
        out.update(centroid_row=None, centroid_col=None, edge_load_fraction=0.0)
    return out


def bed_field(person, step=0.03):
    """Coarse true pressure over the whole bed (mmHg) for the operator view."""
    xs = np.arange(step / 2, BED_W, step)
    ys = np.arange(step / 2, BED_L, step)
    if person is None:
        return np.zeros((len(ys), len(xs)))
    X, Y = np.meshgrid(xs, ys)
    return person.pressure(X, Y) / MMHG


def clamp_person(person):
    """Keep the whole body on the mattress after a move or a turn."""
    xs, ys = person.extent()
    person.x += max(0, -xs.min()) - max(0, xs.max() - BED_W)
    person.y += max(0, -ys.min()) - max(0, ys.max() - BED_L)
    return person


__all__ = [
    "BED_W",
    "BED_L",
    "ROWS",
    "COLS",
    "PX",
    "PY",
    "MAT_W",
    "MAT_L",
    "SCALE",
    "MatPlacement",
    "Person",
    "VirtualMat",
    "measure",
    "bed_field",
    "clamp_person",
]
