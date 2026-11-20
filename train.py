import copy
import json

import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, recall_score

from dataset import LABELS, recording
from model import PostureCNN, inputs

SPLITS = {"train": list(range(1, 9)), "validation": [9, 10], "test": [11, 12, 13]}


def load(subjects):
    xs, ys, ids = [], [], []
    for s in subjects:
        for i in range(3):
            frames = recording(s, i + 1)
            xs.append(inputs(frames, 1000))
            ys.extend([i] * len(frames))
            ids.extend([s] * len(frames))
    return torch.cat(xs), torch.tensor(ys), np.array(ids)


def metrics(y, p):
    return dict(
        accuracy=accuracy_score(y, p),
        macro_f1=f1_score(y, p, average="macro"),
        recall=recall_score(y, p, average=None).tolist(),
        confusion=confusion_matrix(y, p).tolist(),
    )


if __name__ == "__main__":
    torch.manual_seed(41)
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    x, y, _ = load(SPLITS["train"])
    v, w, _ = load(SPLITS["validation"])
    net = PostureCNN()
    optim = torch.optim.Adam(net.parameters(), lr=0.002)
    epochs = []
    best = -1
    for epoch in range(15):
        net.train()
        for batch in torch.randperm(len(x)).split(64):
            optim.zero_grad()
            loss = torch.nn.functional.cross_entropy(net(x[batch]), y[batch])
            loss.backward()
            optim.step()
        with torch.no_grad():
            score = f1_score(w, net.eval()(v).argmax(1), average="macro")
        epochs.append(score)
        if score > best:
            best, weights, selected = score, copy.deepcopy(net.state_dict()), epoch + 1
    net.load_state_dict(weights)
    cfg = dict(
        version="pmat-flat-v1",
        architecture="PostureCNN",
        labels=LABELS,
        cap=1000,
        transform="log1p",
        splits=SPLITS,
        seed=41,
        epoch=selected,
    )
    torch.save(dict(config=cfg, weights=weights), "model.pt")
    z, t, subjects = load(SPLITS["test"])
    with torch.no_grad():
        p = net.eval()(z).argmax(1)
    templates = torch.stack([x[y == i].mean(0) for i in range(3)])
    baseline = torch.cdist(z.flatten(1), templates.flatten(1)).argmin(1)
    results = dict(
        config=cfg,
        count=[len(x), len(v), len(z)],
        validation_macro_f1=epochs,
        cnn=metrics(t, p),
        template=metrics(t, baseline),
        by_subject={
            str(s): metrics(t[subjects == s], p[subjects == s]) for s in SPLITS["test"]
        },
    )
    open("evidence/results.json", "w").write(json.dumps(results, indent=2))
    fig, axes = plt.subplots(1, 3, figsize=(7, 5))
    for i, ax in enumerate(axes):
        ax.imshow(recording(11, i + 1)[40].T, vmin=0, vmax=250, cmap="inferno")
        ax.set_title(LABELS[i])
        ax.axis("off")
    fig.suptitle("PmatData · S11 · original row 41 · display clipped at 250")
    fig.savefig("evidence/frames.png")
