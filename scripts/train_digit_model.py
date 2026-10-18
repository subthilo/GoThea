"""Trainiert das kleine Ziffernmodell für das Schreibfeld (frontend/js/digit_ink.js, Stufe „Gedankengang“).

Läuft NICHT in der App-Umgebung: braucht PyTorch, NumPy und Pillow in einer eigenen venv, z. B.
    python3 -m venv /tmp/ml && /tmp/ml/bin/pip install torch numpy pillow
    /tmp/ml/bin/python scripts/train_digit_model.py --mnist <Ordner mit den 4 MNIST-idx-Dateien> \\
        --shapes <shapes.json> --out frontend/models/digits_cnn.bin

Daten: MNIST (70 000 gescannte Ziffern) plus künstlich verzerrte Ziffern aus den Musterformen in digit_ink.js
(deutsche 1 mit Aufstrich, 7 mit Querstrich, offene 4 …), gerendert GENAU wie im Browser (render_strokes ↔
renderChar in digit_ink.js: 112×112, runde Linien, 4×4-Mittelung auf 28×28, Schwerpunkt in die Mitte).
shapes.json = DigitInk.SHAPES als Punktlisten (im Browser exportiert).

Ausgabe: Gewichte als float32 (little endian) in fester Reihenfolge, siehe LAYERS; dazu eine Messung.
"""
import argparse
import json
import math
import random
import struct
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image, ImageDraw

LAYERS = ["conv1.weight", "conv1.bias", "conv2.weight", "conv2.bias", "fc1.weight", "fc1.bias", "fc2.weight", "fc2.bias"]
RENDER = 112      # Zeichenfläche (4× 28)
BOX = 80          # längste Seite der Ziffer auf der Zeichenfläche (= 20 px bei 28)
LINE = 8          # Strichbreite auf der Zeichenfläche (= 2 px bei 28)


class DigitNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 16, 3)
        self.conv2 = nn.Conv2d(16, 32, 3)
        self.fc1 = nn.Linear(32 * 5 * 5, 64)
        self.fc2 = nn.Linear(64, 10)

    def forward(self, x):
        x = F.max_pool2d(F.relu(self.conv1(x)), 2)   # 28 → 26 → 13
        x = F.max_pool2d(F.relu(self.conv2(x)), 2)   # 13 → 11 → 5
        x = F.dropout(F.relu(self.fc1(x.flatten(1))), 0.25, self.training)
        return self.fc2(x)


def read_idx(path):
    data = Path(path).read_bytes()
    magic, n = struct.unpack(">II", data[:8])
    if magic == 2051:
        rows, cols = struct.unpack(">II", data[8:16])
        return np.frombuffer(data, np.uint8, offset=16).reshape(n, rows, cols)
    return np.frombuffer(data, np.uint8, offset=8)


def center_of_mass(img):
    """Schwerpunkt in die Mitte schieben (ganze Pixel, wie MNIST)."""
    total = img.sum()
    if total <= 0:
        return img
    ys, xs = np.indices(img.shape)
    dy, dx = int(round(13.5 - (ys * img).sum() / total)), int(round(13.5 - (xs * img).sum() / total))
    out = np.zeros_like(img)
    h, w = img.shape
    out[max(0, dy):h + min(0, dy), max(0, dx):w + min(0, dx)] = img[max(0, -dy):h - max(0, dy), max(0, -dx):w - max(0, dx)]
    return out


def render_strokes(strokes, line=LINE):
    """Striche → 28×28 (0..1). Muss renderChar in digit_ink.js entsprechen."""
    pts = [p for s in strokes for p in s]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    scale = BOX / max(w, h, 1e-6)
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    img = Image.new("L", (RENDER, RENDER), 0)
    draw = ImageDraw.Draw(img)
    r = line / 2
    for s in strokes:
        q = [((x - cx) * scale + RENDER / 2, (y - cy) * scale + RENDER / 2) for x, y in s]
        if len(q) > 1:
            draw.line(q, fill=255, width=line)
        for x, y in q:  # runde Enden und Ecken
            draw.ellipse([x - r, y - r, x + r, y + r], fill=255)
    a = np.asarray(img, np.float32).reshape(28, 4, 28, 4).mean(axis=(1, 3)) / 255.0
    return center_of_mass(a)


def distort(strokes, rng, strength=1.0):
    """Musterziffer → zufällige „Handschrift“: schmaler, schräg, gedreht, wacklig."""
    aspect = rng.uniform(0.45, 0.8)
    skew = rng.uniform(-0.35, 0.35) * strength
    rot = rng.uniform(-0.22, 0.22) * strength
    amp, ph = rng.uniform(0, 0.025) * strength, rng.uniform(0, 6)
    c, s_ = math.cos(rot), math.sin(rot)
    out = []
    for stroke in strokes:
        dense = []
        for a, b in zip(stroke, stroke[1:] + [stroke[-1]]):
            for t in (0, 0.25, 0.5, 0.75):
                dense.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        q = []
        for i, (x, y) in enumerate(dense):
            x = (x * aspect + skew * (1 - y))
            X, Y = x * c - y * s_, x * s_ + y * c
            q.append((X + amp * math.sin(i / 5 + ph), Y + amp * math.cos(i / 7 + ph)))
        out.append(q)
    # mal ein Strich etwas verkürzt oder verschoben (unsauberes Ansetzen)
    if len(out) > 1 and rng.random() < 0.4:
        k = rng.randrange(len(out))
        dx, dy = rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05)
        out[k] = [(x + dx, y + dy) for x, y in out[k]]
    return out


def synthetic(shapes, n, seed):
    rng = random.Random(seed)
    xs, ys = [], []
    labels = sorted(shapes)
    for i in range(n):
        label = labels[i % 10]
        strokes = rng.choice(shapes[label])
        xs.append(render_strokes(distort(strokes, rng), line=rng.choice([6, 7, 8, 9, 10])))
        ys.append(int(label))
    return np.stack(xs), np.array(ys)


def augment(x):
    """Leichte zufällige Verformung je Stapel (Drehung, Scherung, Größe, Verschiebung)."""
    n = x.shape[0]
    ang = (torch.rand(n) - 0.5) * math.radians(20)
    shear = (torch.rand(n) - 0.5) * 0.3
    sc = 1 + (torch.rand(n) - 0.5) * 0.2
    tx, ty = (torch.rand(n) - 0.5) * 0.15, (torch.rand(n) - 0.5) * 0.15
    cos, sin = torch.cos(ang) / sc, torch.sin(ang) / sc
    theta = torch.stack([torch.stack([cos, -sin + shear, tx], 1), torch.stack([sin, cos, ty], 1)], 1)
    grid = F.affine_grid(theta, x.shape, align_corners=False)
    return F.grid_sample(x, grid, align_corners=False)


def accuracy(model, x, y):
    model.eval()
    with torch.no_grad():
        pred = torch.cat([model(x[i:i + 2000]).argmax(1) for i in range(0, len(x), 2000)])
    return (pred == y).float().mean().item()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mnist", required=True)
    ap.add_argument("--shapes", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--epochs", type=int, default=6)
    args = ap.parse_args()
    torch.manual_seed(0)

    m = Path(args.mnist)
    xtr = read_idx(m / "train-images-idx3-ubyte").astype(np.float32) / 255
    ytr = read_idx(m / "train-labels-idx1-ubyte").astype(np.int64)
    xte = read_idx(m / "t10k-images-idx3-ubyte").astype(np.float32) / 255
    yte = read_idx(m / "t10k-labels-idx1-ubyte").astype(np.int64)
    shapes = json.loads(Path(args.shapes).read_text())
    sx, sy = synthetic(shapes, 30000, seed=1)
    stx, sty = synthetic(shapes, 3000, seed=99)

    x = torch.tensor(np.concatenate([xtr, sx]))[:, None]
    y = torch.tensor(np.concatenate([ytr, sy]))
    model = DigitNet()
    opt = torch.optim.Adam(model.parameters(), lr=2e-3)
    sched = torch.optim.lr_scheduler.StepLR(opt, step_size=2, gamma=0.5)
    for epoch in range(args.epochs):
        model.train()
        perm = torch.randperm(len(x))
        for i in range(0, len(x), 128):
            idx = perm[i:i + 128]
            loss = F.cross_entropy(model(augment(x[idx])), y[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
        sched.step()
        print(f"Epoche {epoch + 1}: MNIST-Test {accuracy(model, torch.tensor(xte)[:, None], torch.tensor(yte)):.4f}, "
              f"Muster-Test {accuracy(model, torch.tensor(stx)[:, None], torch.tensor(sty)):.4f}", flush=True)

    state = model.state_dict()
    blob = b"".join(state[k].detach().numpy().astype("<f4").tobytes() for k in LAYERS)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_bytes(blob)
    print(f"{args.out}: {len(blob)} Bytes")
    # Prüfbild für den Abgleich mit dem Browser-Renderer
    probe = render_strokes(shapes["4"][0])
    Path(args.out).with_suffix(".probe.json").write_text(json.dumps({
        "strokes": shapes["4"][0], "pixels": [round(float(v), 4) for v in probe.flatten()],
        "logits": [round(float(v), 4) for v in model.eval()(torch.tensor(probe)[None, None]).detach()[0]],
    }))


if __name__ == "__main__":
    main()
