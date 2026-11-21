"""Top-down body contact model for the interactive virtual bed.

The person is a set of body segments resting on an elastic (Winkler) mattress.
Each segment is a capsule: a line from P0 to P1 in the body frame with a
rounded underside of curvature radius rho, cut off at the segment's half-width
w. A point at distance d from the segment's axis sits h = d^2 / (2 rho) above
the segment's lowest line. The segment sinks s into the mattress, and the
mattress pushes back with

    p = k * max(0, s - h)        [Pa],   only where d <= w

Each segment carries a share of body weight from standard segment-mass tables;
bony prominences (sacrum, shoulder blades, heels, hip, shoulder, knee, ankle)
are short stiff segments that take part of their region's load. The sink s of
every segment is solved once, numerically, so its pressure integrates to its
weight exactly. The bed is flat and uniform, so s does not depend on where the
person lies, only on posture. No recordings, templates or model weights are
inputs to this file.

Body frame: b is lateral, positive toward the person's LEFT hand when lying on
their back. a is longitudinal, positive toward the feet. The origin is the
pelvis (hip-joint centre), which is also the drag handle in the interface.

Bed frame: metres from the top-left corner of the mattress viewed from above,
X to the right, Y toward the foot of the bed. theta (degrees) turns the person
clockwise on screen; theta = 0 puts the head at the head of the bed.
"""

from dataclasses import dataclass

import numpy as np

G = 9.81
MMHG = 133.322  # pascals per mmHg
K_FOUNDATION = 2.2e5  # Pa per metre of mattress compression
MASS_KG = 75.0
HEIGHT_M = 1.75

# name, (b0, a0), (b1, a1), rho, half-width w, weight share. Lying on the back.
SUPINE = [
    ("head", (0.0, -0.77), (0.0, -0.71), 0.070, 0.075, 0.070),
    ("thorax", (0.0, -0.55), (0.0, -0.30), 0.220, 0.175, 0.190),
    ("scapula L", (0.085, -0.52), (0.085, -0.46), 0.060, 0.060, 0.040),
    ("scapula R", (-0.085, -0.52), (-0.085, -0.46), 0.060, 0.060, 0.040),
    ("lumbar", (0.0, -0.28), (0.0, -0.13), 0.260, 0.150, 0.045),
    ("pelvis", (0.0, -0.11), (0.0, 0.05), 0.200, 0.180, 0.150),
    ("sacrum", (0.0, -0.07), (0.0, -0.02), 0.050, 0.050, 0.060),
    ("thigh L", (0.09, 0.08), (0.10, 0.42), 0.075, 0.080, 0.070),
    ("thigh R", (-0.09, 0.08), (-0.10, 0.42), 0.075, 0.080, 0.070),
    ("calf L", (0.10, 0.50), (0.11, 0.82), 0.050, 0.055, 0.032),
    ("calf R", (-0.10, 0.50), (-0.11, 0.82), 0.050, 0.055, 0.032),
    ("heel L", (0.11, 0.87), (0.11, 0.90), 0.030, 0.032, 0.016),
    ("heel R", (-0.11, 0.87), (-0.11, 0.90), 0.030, 0.032, 0.016),
    ("upper arm L", (0.22, -0.53), (0.24, -0.29), 0.040, 0.045, 0.025),
    ("upper arm R", (-0.22, -0.53), (-0.24, -0.29), 0.040, 0.045, 0.025),
    ("forearm L", (0.25, -0.26), (0.26, 0.01), 0.035, 0.040, 0.018),
    ("forearm R", (-0.25, -0.26), (-0.26, 0.01), 0.035, 0.040, 0.018),
]

# Lying on the RIGHT side. The trunk turns about its own long axis, so the
# right flank lands near where the spine was. The chest faces the person's
# right (negative b); hips and knees flex, so the legs and folded arms rest in
# front of the trunk.
RIGHT_SIDE = [
    ("head", (-0.02, -0.77), (-0.02, -0.71), 0.060, 0.065, 0.070),
    ("shoulder", (0.0, -0.54), (0.0, -0.49), 0.050, 0.060, 0.095),
    ("lateral thorax", (0.0, -0.52), (0.01, -0.30), 0.120, 0.100, 0.140),
    ("waist", (0.01, -0.28), (0.02, -0.12), 0.120, 0.070, 0.030),
    ("lateral pelvis", (0.02, -0.11), (0.02, 0.06), 0.120, 0.110, 0.120),
    ("greater trochanter", (0.02, -0.02), (0.02, 0.02), 0.035, 0.040, 0.090),
    ("lower thigh", (0.0, 0.06), (-0.17, 0.36), 0.070, 0.070, 0.080),
    ("upper thigh", (-0.05, 0.08), (-0.22, 0.36), 0.060, 0.060, 0.050),
    ("lower knee", (-0.17, 0.37), (-0.17, 0.40), 0.030, 0.035, 0.040),
    ("lower shin", (-0.17, 0.41), (-0.10, 0.80), 0.050, 0.050, 0.050),
    ("upper shin", (-0.23, 0.41), (-0.20, 0.78), 0.045, 0.045, 0.040),
    ("lower ankle", (-0.10, 0.83), (-0.10, 0.86), 0.025, 0.030, 0.020),
    ("upper foot", (-0.20, 0.82), (-0.20, 0.86), 0.025, 0.030, 0.015),
    ("folded arms", (-0.18, -0.52), (-0.22, -0.24), 0.050, 0.050, 0.050),
]


def _table(rows):
    t = np.array([(*p0, *p1, rho, w, share) for _, p0, p1, rho, w, share in rows])
    t[:, 6] /= t[:, 6].sum()
    return t


def _segment_distance(b, a, seg):
    b0, a0, b1, a1 = seg[:4]
    db, da = b1 - b0, a1 - a0
    length2 = db * db + da * da
    u = np.clip(((b - b0) * db + (a - a0) * da) / length2, 0, 1)
    return np.hypot(b - (b0 + u * db), a - (a0 + u * da))


def _solve_sinks(table, mass=MASS_KG):
    """Bisection for each segment's sink so its pressure integrates to its load."""
    step = 0.004
    sinks = []
    for seg in table:
        rho, w, share = seg[4:7]
        force = share * mass * G
        b0, a0, b1, a1 = seg[:4]
        lo_b, hi_b = min(b0, b1) - w, max(b0, b1) + w
        lo_a, hi_a = min(a0, a1) - w, max(a0, a1) + w
        B, A = np.meshgrid(
            np.arange(lo_b, hi_b + step, step), np.arange(lo_a, hi_a + step, step)
        )
        d = _segment_distance(B, A, seg)
        h = np.where(d <= w, d * d / (2 * rho), np.inf)
        lo, hi = 0.0, 0.5
        for _ in range(60):
            s = (lo + hi) / 2
            f = K_FOUNDATION * np.maximum(0, s - h).sum() * step * step
            lo, hi = (s, hi) if f < force else (lo, s)
        sinks.append((lo + hi) / 2)
    return np.array(sinks)


SUPINE_T = _table(SUPINE)
RIGHT_T = _table(RIGHT_SIDE)
LEFT_T = RIGHT_T * np.array([-1, 1, -1, 1, 1, 1, 1])  # mirror across the spine
SINKS = {
    "back": _solve_sinks(SUPINE_T),
    "right": _solve_sinks(RIGHT_T),
    "left": _solve_sinks(LEFT_T),
}
TABLES = {"back": SUPINE_T, "right": RIGHT_T, "left": LEFT_T}


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _field(b, a, table, sinks, breath):
    p = np.zeros(np.broadcast(b, a).shape)
    for seg, s in zip(table, sinks):
        rho, w = seg[4], seg[5]
        if seg[1] < -0.3:  # breathing moves a little load on and off the chest
            s = s * (1 + 0.015 * np.sin(breath))
        d = _segment_distance(b, a, seg)
        inside = d <= w
        p += np.where(inside, np.maximum(0, s - d * d / (2 * rho)), 0)
    return K_FOUNDATION * p


@dataclass
class Person:
    """Operator-controlled ground truth. Never sent to the model."""

    x: float = 0.76  # pelvis, metres from the bed's left edge
    y: float = 0.98  # pelvis, metres from the head of the bed
    theta: float = 0.0  # degrees clockwise on screen
    roll: float = 0.0  # -1 left side, 0 back, +1 right side
    breath: float = 0.0  # breathing phase in radians
    mass: float = MASS_KG  # fixed; the sinks are solved for this mass

    def local(self, X, Y):
        th = np.radians(self.theta)
        dx, dy = X - self.x, Y - self.y
        return dx * np.cos(th) + dy * np.sin(th), -dx * np.sin(th) + dy * np.cos(th)

    def pressure(self, X, Y):
        """True contact pressure in pascals at bed points X, Y (metres).

        A roll blends the two postures' load paths, p = (1-t) p_back + t p_side,
        which keeps the total load equal to body weight throughout the turn.
        """
        b, a = self.local(X, Y)
        r = float(np.clip(self.roll, -1, 1))
        t = float(smoothstep(abs(r)))
        side = "right" if r >= 0 else "left"
        p = 0.0
        if t < 1:
            p = (1 - t) * _field(b, a, SUPINE_T, SINKS["back"], self.breath)
        if t > 0:
            p = p + t * _field(b, a, TABLES[side], SINKS[side], self.breath)
        return p * np.ones(np.broadcast(X, Y).shape)

    def extent(self):
        """Bed-frame corners of the body's bounding box, for clamping."""
        th = np.radians(self.theta)
        b = np.array([-0.31, 0.31, -0.31, 0.31])
        a = np.array([-0.82, -0.82, 0.92, 0.92])
        return (
            self.x + b * np.cos(th) - a * np.sin(th),
            self.y + b * np.sin(th) + a * np.cos(th),
        )
