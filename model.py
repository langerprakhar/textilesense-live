import numpy as np
import torch
from torch import nn


def inputs(raw, cap):
    return torch.from_numpy(
        np.log1p(np.clip(raw, 0, cap)).astype("float32") / np.float32(np.log1p(cap))
    ).reshape(-1, 1, 32, 64)


class PostureCNN(nn.Sequential):
    def __init__(self):
        super().__init__(
            nn.Conv2d(1, 8, 5, padding=2),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(8, 16, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.AdaptiveAvgPool2d((4, 8)),
            nn.Flatten(),
            nn.Linear(512, 3),
        )
