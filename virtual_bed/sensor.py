"""Procedural contact model. No recordings, templates, or model weights are inputs."""

import numpy as np


class Mat:
    def __init__(self, seed=41):
        self.x, self.y = np.indices((32, 64))
        self.rng = np.random.default_rng(seed)
        self.contact = np.zeros((32, 64))
        self.tick = 0

    def sample(self, pose):
        self.tick += 1
        target = np.zeros_like(self.contact)
        if pose != "empty":
            side = {"back": 0, "left": -1, "right": 1}[pose]
            center = 15.5 + 3 * side + 0.2 * np.sin(self.tick / 7)
            width = 1 if side == 0 else 0.62

            # Locations and spreads are in sensor cells. Amplitudes are arbitrary counts.
            def patch(dx, y, wx, wy, strength):
                lateral = (self.x - center - dx * width) / (wx * width)
                longitudinal = (self.y - y) / wy
                target[:] += strength * np.exp(-0.5 * (lateral**2 + longitudinal**2))

            patch(0, 7, 2.8, 3, 190)
            patch(0, 22, 5, 6, 95 + 4 * np.sin(self.tick * 1.4))
            patch(0, 34, 4.8, 4, 165)
            for sign in (-1, 1):
                load = 1 + 0.55 * sign * side
                patch(sign * 5, 17, 2.3, 2.5, 92 * load)
                patch(sign * 3, 34, 2, 2.7, 125 * load)
                patch(sign * 3, 44, 1.9, 5, 85 * load)
                patch(sign * 3, 57, 1.4, 2.2, 130 * load)
        self.contact += 0.75 * (target - self.contact)
        noise = self.rng.normal(0, 0.025, self.contact.shape)
        return np.rint(self.contact * (1 + noise)).clip(0, 1000).astype(int)
