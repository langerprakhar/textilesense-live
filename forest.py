"""Independent spatial-feature baseline using the same participant split."""

import json

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from train import SPLITS, load, metrics


def features(x):
    # 4 lateral bands by 8 longitudinal bands, each covering 8 x 8 sensors.
    blocks = x.numpy().reshape(-1, 4, 8, 8, 8)
    return np.concatenate(
        [
            a.reshape(len(x), -1)
            for a in (
                blocks.mean((2, 4)),
                blocks.max((2, 4)),
                (blocks > 0).mean((2, 4)),
            )
        ],
        axis=1,
    )


if __name__ == "__main__":
    x, y, _ = load(SPLITS["train"])
    z, t, _ = load(SPLITS["test"])
    clf = RandomForestClassifier(
        n_estimators=100, min_samples_leaf=3, random_state=41, n_jobs=2
    )
    clf.fit(features(x), y)
    print(json.dumps(metrics(t, clf.predict(features(z))), indent=2))
