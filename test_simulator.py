"""Physical and geometric checks of the virtual bed. No services needed."""

import numpy as np
import pytest

from virtual_bed.body import G, Person
from virtual_bed.sensor import (
    BED_W,
    MAT_W,
    PX,
    MatPlacement,
    VirtualMat,
    clamp_person,
    measure,
)

MAT = MatPlacement()
CX, HIP = MAT.x + MAT_W / 2, MAT.y + 0.89
ROLLS = {"back": 0.0, "left": -1.0, "right": 1.0}


def read(person, mat=MAT, noise=False):
    return VirtualMat(seed=3).read(person, mat, noise=noise)


def test_empty_mat_reads_exact_zeros():
    grid, truth = read(None)
    assert grid.shape == (32, 64) and grid.dtype.kind == "i"
    assert grid.max() == 0 and truth["on_bed"] is False
    noisy, _ = VirtualMat().read(None, MAT, noise=True)
    assert noisy.max() == 0


@pytest.mark.parametrize("posture", ROLLS)
def test_weight_is_conserved_on_a_full_mat(posture):
    p = Person(x=CX, y=HIP, roll=ROLLS[posture])
    grid, truth = read(p)
    assert truth["coverage"] > 0.99
    m = measure(grid)
    assert m["load_kg"] == pytest.approx(p.mass, rel=0.03)
    assert 30 < m["peak_mmhg"] < 200


@pytest.mark.parametrize("roll", [0.25, 0.5, 0.75])
def test_weight_is_conserved_mid_roll(roll):
    _, truth = read(Person(x=CX, y=HIP, roll=roll))
    assert truth["mat_force_n"] == pytest.approx(75 * G, rel=0.01)


@pytest.mark.parametrize("theta", [-10.0, 10.0, 25.0, 90.0])
def test_turning_conserves_weight(theta):
    p = Person(x=0.76, y=1.0, theta=theta)
    xs, ys = np.meshgrid(np.arange(-0.5, 2.1, 0.004), np.arange(-0.5, 2.6, 0.004))
    total = p.pressure(xs, ys).sum() * 0.004**2
    assert total == pytest.approx(75 * G, rel=0.01)


def test_sliding_moves_the_measured_pattern_continuously():
    previous, rows, deltas = None, [], []
    for i in range(11):
        grid, _ = read(Person(x=CX - 0.05 + i * 0.01, y=HIP))
        m = measure(grid)
        rows.append(m["centroid_row"])
        if previous is not None:
            deltas.append(np.abs(grid - previous).sum() / grid.sum())
        previous = grid
    # Row 0 is on the right, so moving right lowers the row number by 1 per 2.4 cm.
    assert all(b < a for a, b in zip(rows, rows[1:]))
    assert rows[0] - rows[-1] == pytest.approx(0.10 / PX, rel=0.1)
    assert max(deltas) < 0.6  # every 1 cm step is a small change, never a jump


def test_head_to_foot_motion_moves_columns():
    a = measure(read(Person(x=CX, y=HIP - 0.05))[0])["centroid_col"]
    b = measure(read(Person(x=CX, y=HIP + 0.05))[0])["centroid_col"]
    assert b - a == pytest.approx(0.10 / 0.029, rel=0.1)


def test_body_off_the_mat_is_not_measured():
    mat = MatPlacement(x=0.0).clamp()  # mat against the bed's left edge
    far = clamp_person(Person(x=BED_W - 0.05, y=HIP))
    grid, truth = read(far, mat)
    assert grid.max() == 0 and truth["coverage"] == 0
    for x in (0.70, 0.80, 0.90):
        grid, truth = read(Person(x=x, y=HIP), mat)
        assert 0 < truth["coverage"] < 1
        # the 1 mmHg dead band drops a few newtons of faint fringe load
        assert measure(grid)["load_n"] == pytest.approx(truth["mat_force_n"], rel=0.03, abs=8)


def test_partial_coverage_shrinks_monotonically():
    mat = MatPlacement(x=0.0).clamp()
    cover = [read(Person(x=x, y=HIP), mat)[1]["coverage"] for x in (0.5, 0.65, 0.8, 0.95, 1.1)]
    assert all(b < a for a, b in zip(cover, cover[1:]))


def test_left_and_right_are_mirror_images():
    left, _ = read(Person(x=CX, y=HIP, roll=-1))
    right, _ = read(Person(x=CX, y=HIP, roll=1))
    assert np.abs(left - right[::-1, :]).sum() / left.sum() < 0.02


def test_orientation_matches_the_training_recordings():
    # In PmatData "Right" frames the flexed knees sit at higher row numbers
    # than the hips; "Left" frames the opposite.
    def knee_minus_hip(grid):
        def centre(c0, c1):
            w = grid[:, c0:c1].sum(1)
            return (w * np.arange(32)).sum() / w.sum()

        return centre(40, 48) - centre(28, 36)

    assert knee_minus_hip(read(Person(x=CX, y=HIP, roll=1))[0]) > 3
    assert knee_minus_hip(read(Person(x=CX, y=HIP, roll=-1))[0]) < -3


def test_noise_changes_frames_but_not_their_meaning():
    sensor = VirtualMat(seed=5)
    p = Person(x=CX, y=HIP)
    a, _ = sensor.read(p, MAT)
    b, _ = sensor.read(p, MAT)
    assert (a != b).any()
    assert measure(a)["load_kg"] == pytest.approx(measure(b)["load_kg"], rel=0.02)


def test_person_is_kept_on_the_mattress():
    p = clamp_person(Person(x=-1.0, y=5.0, theta=30))
    assert p.x > 0 and p.y < 2.03
