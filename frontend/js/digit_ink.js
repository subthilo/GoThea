// ==========================================================================
// Ziffern aus Pencil-Strichen erkennen (Schreibfeld der Stufe „Gedankengang“)
// --------------------------------------------------------------------------
// Ohne KI-Dienst und ohne Wartezeit, direkt im Browser:
//   1. segment(): Striche nach links/rechts zu Zeichen gruppieren (überlappende
//      oder sich berührende Striche gehören zusammen, z. B. die zwei Striche einer
//      4); ein kleiner, schmaler Strich unten ist ein Komma.
//   2. renderChar(): jedes Zeichen wie im Training zu einem 28×28-Bild machen
//      (112×112 zeichnen, runde Linien, 4×4 mitteln, Schwerpunkt in die Mitte).
//   3. classify(): kleines faltendes Netz (models/digits_cnn.bin, trainiert mit
//      scripts/train_digit_model.py auf MNIST + verzerrten Musterziffern).
// renderChar und das Netz müssen exakt zu render_strokes/DigitNet im Trainings-
// skript passen. SHAPES (Musterziffern) dienen dem Training und den Tests.
// Striche im Format des Zeichenkerns: { points: [{ x, y }, …] }.
// ==========================================================================

const DigitInk = (function () {
  const MODEL_URL = "/static/models/digits_cnn.bin";
  const UNSURE_PROBABILITY = 0.6;  // darunter gilt ein Zeichen als nicht lesbar („?“)
  const RENDER = 112, BOX = 80, LINE = 8;

  // ---------- Mitgelieferte Musterziffern (im Einheitsquadrat, y nach unten) ----------
  // Je Ziffer mehrere übliche Schreibweisen; Kurven werden aus Stützpunkten geglättet.

  function curve(points, steps = 6) {
    const out = [];
    const at = (i) => points[Math.max(0, Math.min(points.length - 1, i))];
    for (let i = 0; i < points.length - 1; i++) {
      const p0 = at(i - 1), p1 = at(i), p2 = at(i + 1), p3 = at(i + 2);
      for (let s = 0; s < steps; s++) {
        const t = s / steps, t2 = t * t, t3 = t2 * t;
        out.push({
          x: 0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
          y: 0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3),
        });
      }
    }
    const last = points[points.length - 1];
    out.push({ x: last[0], y: last[1] });
    return { points: out };
  }
  const line = (...pts) => ({ points: pts.map(([x, y]) => ({ x, y })) });
  function ellipse(cx, cy, rx, ry, from = -Math.PI / 2, to = 1.5 * Math.PI, steps = 24) {
    const pts = [];
    for (let i = 0; i <= steps; i++) {
      const a = from + (to - from) * (i / steps);
      pts.push({ x: cx + rx * Math.cos(a), y: cy + ry * Math.sin(a) });
    }
    return { points: pts };
  }

  const SHAPES = {
    "0": [[ellipse(0.5, 0.5, 0.32, 0.5)], [ellipse(0.5, 0.5, 0.25, 0.5, -Math.PI / 2, 1.6 * Math.PI)]],
    "1": [
      [line([0.5, 0], [0.5, 1])],
      [line([0.25, 0.3], [0.55, 0], [0.55, 1])],
      [line([0.25, 0.3], [0.55, 0], [0.55, 1]), line([0.3, 1], [0.8, 1])],
    ],
    "2": [
      [curve([[0.15, 0.25], [0.45, 0.02], [0.82, 0.22], [0.65, 0.55], [0.12, 1], [0.9, 1]])],
      [curve([[0.18, 0.2], [0.5, 0], [0.85, 0.28], [0.15, 0.98]]), line([0.15, 0.98], [0.9, 0.98])],
    ],
    "3": [
      [curve([[0.15, 0.12], [0.55, 0.0], [0.82, 0.22], [0.45, 0.48], [0.85, 0.72], [0.55, 1], [0.12, 0.88]])],
      [line([0.15, 0.02], [0.85, 0.02], [0.45, 0.42]), curve([[0.45, 0.42], [0.85, 0.65], [0.6, 1], [0.12, 0.88]])],
    ],
    "4": [
      [line([0.65, 0], [0.08, 0.68], [0.92, 0.68]), line([0.68, 0.3], [0.68, 1])],
      [line([0.25, 0], [0.15, 0.6], [0.88, 0.6]), line([0.7, 0], [0.7, 1])],
      [line([0.2, 0], [0.15, 0.6], [0.85, 0.6]), line([0.7, 0.3], [0.7, 1])],
    ],
    "5": [
      [line([0.82, 0.02], [0.25, 0.02], [0.2, 0.45]), curve([[0.2, 0.45], [0.6, 0.38], [0.85, 0.68], [0.55, 1], [0.12, 0.9]])],
      [curve([[0.25, 0.02], [0.2, 0.45], [0.6, 0.38], [0.85, 0.68], [0.55, 1], [0.12, 0.9]]), line([0.25, 0.02], [0.82, 0.02])],
    ],
    "6": [
      [curve([[0.75, 0.04], [0.35, 0.3], [0.18, 0.7], [0.45, 1], [0.8, 0.78], [0.55, 0.5], [0.2, 0.68]])],
      [curve([[0.7, 0], [0.3, 0.35], [0.2, 0.72], [0.5, 0.98], [0.78, 0.72], [0.48, 0.52], [0.22, 0.7]])],
    ],
    "7": [
      [line([0.1, 0.02], [0.9, 0.02], [0.38, 1])],
      [line([0.1, 0.02], [0.9, 0.02], [0.38, 1]), line([0.3, 0.52], [0.78, 0.52])],
      [line([0.1, 0.15], [0.12, 0.02], [0.9, 0.02], [0.45, 1])],
    ],
    "8": [
      [curve([[0.75, 0.15], [0.5, 0.02], [0.25, 0.2], [0.5, 0.48], [0.82, 0.75], [0.5, 1], [0.18, 0.75], [0.5, 0.48], [0.75, 0.2], [0.72, 0.12]])],
      [ellipse(0.5, 0.25, 0.22, 0.24), ellipse(0.5, 0.74, 0.28, 0.26)],
    ],
    "9": [
      [curve([[0.78, 0.25], [0.5, 0.02], [0.22, 0.25], [0.45, 0.5], [0.78, 0.32], [0.78, 0.25], [0.75, 1]])],
      [ellipse(0.5, 0.27, 0.28, 0.25), line([0.78, 0.25], [0.72, 1])],
      [curve([[0.78, 0.25], [0.5, 0.02], [0.22, 0.25], [0.45, 0.5], [0.78, 0.32], [0.7, 0.75], [0.4, 1]])],
    ],
  };

  // ---------- Zeichen trennen ----------

  function box(points) {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    points.forEach((p) => { minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x); minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y); });
    return { minX, minY, maxX, maxY, w: maxX - minX, h: maxY - minY };
  }

  // Berühren sich zwei Strichgruppen (z. B. Bauch und Strich einer 9)?
  function touching(a, b, gap) {
    const pa = a.flatMap((s) => s.points), pb = b.flatMap((s) => s.points);
    const step = Math.max(1, Math.floor(pa.length / 40)), stepB = Math.max(1, Math.floor(pb.length / 40));
    for (let i = 0; i < pa.length; i += step) {
      for (let j = 0; j < pb.length; j += stepB) {
        if (Math.hypot(pa[i].x - pb[j].x, pa[i].y - pb[j].y) < gap) return true;
      }
    }
    return false;
  }

  function segment(strokes) {
    const items = strokes.filter((s) => s.points && s.points.length).map((s) => ({ strokes: [s], box: box(s.points) }));
    if (!items.length) return [];
    const top = Math.min(...items.map((i) => i.box.minY)), bottom = Math.max(...items.map((i) => i.box.maxY));
    const lineH = Math.max(bottom - top, 1);
    // Komma: klein, schmal, unten (der Fuß einer 1 ist breiter und gehört zur 1)
    const isComma = (b) => b.h < 0.35 * lineH && b.w < 0.25 * lineH && (b.minY + b.maxY) / 2 > top + 0.6 * lineH;
    items.sort((a, b) => a.box.minX - b.box.minX);
    const groups = [];
    for (const item of items) {
      const last = groups[groups.length - 1];
      // Liegt der kleine Strich größtenteils unter der Ziffer davor, ist er ihr Teil (Fuß der 1), kein Komma
      const under = last && Math.min(last.box.maxX, item.box.maxX) - Math.max(last.box.minX, item.box.minX) > 0.5 * item.box.w;
      const comma = isComma(item.box) && !under;
      if (last && !comma && !last.comma) {
        // Gleiches Zeichen, wenn sich die Striche waagerecht deutlich überdecken oder einer mitten im
        // anderen steht (senkrechter Strich der 4, Querstrich der 7)
        const overlap = Math.min(last.box.maxX, item.box.maxX) - Math.max(last.box.minX, item.box.minX);
        const narrowest = Math.max(Math.min(last.box.w, item.box.w), 0.08 * lineH);
        const inside = (a, b) => (a.minX + a.maxX) / 2 > b.minX + 0.05 * lineH && (a.minX + a.maxX) / 2 < b.maxX - 0.05 * lineH;
        const touches = overlap > 0 && touching(item.strokes, last.strokes, 0.08 * lineH);
        if (overlap >= 0.3 * narrowest || inside(item.box, last.box) || inside(last.box, item.box) || touches) {
          last.strokes.push(...item.strokes);
          last.box = box([...last.strokes.flatMap((s) => s.points)]);
          continue;
        }
      }
      groups.push({ strokes: [...item.strokes], box: item.box, comma });
    }
    return groups;
  }

  // ---------- Bild wie im Training ----------

  function renderChar(strokes) {
    const pts = strokes.flatMap((s) => s.points);
    const b = box(pts);
    const scale = BOX / Math.max(b.w, b.h, 1e-6);
    const cx = (b.minX + b.maxX) / 2, cy = (b.minY + b.maxY) / 2;
    const canvas = document.createElement("canvas");
    canvas.width = RENDER;
    canvas.height = RENDER;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, RENDER, RENDER);
    ctx.strokeStyle = ctx.fillStyle = "#fff";
    ctx.lineWidth = LINE;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    const map = (p) => [(p.x - cx) * scale + RENDER / 2, (p.y - cy) * scale + RENDER / 2];
    strokes.forEach((s) => {
      const q = s.points.map(map);
      if (q.length === 1) {
        ctx.beginPath();
        ctx.arc(q[0][0], q[0][1], LINE / 2, 0, Math.PI * 2);
        ctx.fill();
        return;
      }
      ctx.beginPath();
      ctx.moveTo(q[0][0], q[0][1]);
      q.slice(1).forEach(([x, y]) => ctx.lineTo(x, y));
      ctx.stroke();
    });
    const data = ctx.getImageData(0, 0, RENDER, RENDER).data;
    const img = new Float32Array(28 * 28);
    for (let y = 0; y < 28; y++) {
      for (let x = 0; x < 28; x++) {
        let sum = 0;
        for (let dy = 0; dy < 4; dy++) for (let dx = 0; dx < 4; dx++) sum += data[((y * 4 + dy) * RENDER + x * 4 + dx) * 4];
        img[y * 28 + x] = sum / 16 / 255;
      }
    }
    return centerOfMass(img);
  }

  function centerOfMass(img) {
    let total = 0, sx = 0, sy = 0;
    for (let y = 0; y < 28; y++) for (let x = 0; x < 28; x++) { const v = img[y * 28 + x]; total += v; sx += x * v; sy += y * v; }
    if (total <= 0) return img;
    const dx = Math.round(13.5 - sx / total), dy = Math.round(13.5 - sy / total);
    const out = new Float32Array(28 * 28);
    for (let y = 0; y < 28; y++) {
      for (let x = 0; x < 28; x++) {
        const ty = y + dy, tx = x + dx;
        if (ty >= 0 && ty < 28 && tx >= 0 && tx < 28) out[ty * 28 + tx] = img[y * 28 + x];
      }
    }
    return out;
  }

  // ---------- Netz (wie DigitNet im Trainingsskript) ----------

  let weights = null;
  let loading = null;

  function load() {
    if (!loading) {
      loading = fetch(MODEL_URL, { cache: "no-cache" })
        .then((res) => { if (!res.ok) throw new Error(`HTTP ${res.status}`); return res.arrayBuffer(); })
        .then((buf) => {
          const all = new Float32Array(buf);
          const sizes = [["c1w", 144], ["c1b", 16], ["c2w", 4608], ["c2b", 32], ["f1w", 51200], ["f1b", 64], ["f2w", 640], ["f2b", 10]];
          let at = 0;
          weights = {};
          sizes.forEach(([name, n]) => { weights[name] = all.subarray(at, at + n); at += n; });
          if (at !== all.length) throw new Error("Modell hat eine unerwartete Größe");
        })
        .catch((err) => { console.warn("Ziffernmodell nicht geladen:", err); weights = null; });
    }
    return loading;
  }

  function convReluPool(input, size, cin, w, b, cout) {
    const conv = size - 2, pooled = Math.floor(conv / 2);
    const out = new Float32Array(cout * pooled * pooled);
    const tmp = new Float32Array(conv * conv);
    for (let o = 0; o < cout; o++) {
      for (let y = 0; y < conv; y++) {
        for (let x = 0; x < conv; x++) {
          let sum = b[o];
          for (let c = 0; c < cin; c++) {
            const wBase = ((o * cin + c) * 3) * 3, iBase = c * size * size;
            for (let ky = 0; ky < 3; ky++) {
              for (let kx = 0; kx < 3; kx++) sum += w[wBase + ky * 3 + kx] * input[iBase + (y + ky) * size + x + kx];
            }
          }
          tmp[y * conv + x] = sum > 0 ? sum : 0;
        }
      }
      for (let y = 0; y < pooled; y++) {
        for (let x = 0; x < pooled; x++) {
          const i = 2 * y * conv + 2 * x;
          out[o * pooled * pooled + y * pooled + x] = Math.max(tmp[i], tmp[i + 1], tmp[i + conv], tmp[i + conv + 1]);
        }
      }
    }
    return out;
  }

  function dense(input, w, b, n, relu) {
    const out = new Float32Array(n);
    for (let o = 0; o < n; o++) {
      let sum = b[o];
      for (let i = 0; i < input.length; i++) sum += w[o * input.length + i] * input[i];
      out[o] = relu && sum < 0 ? 0 : sum;
    }
    return out;
  }

  function logits(img) {
    const a = convReluPool(img, 28, 1, weights.c1w, weights.c1b, 16);
    const b = convReluPool(a, 13, 16, weights.c2w, weights.c2b, 32);
    return dense(dense(b, weights.f1w, weights.f1b, 64, true), weights.f2w, weights.f2b, 10, false);
  }

  function classify(strokes) {
    const z = logits(renderChar(strokes));
    const max = Math.max(...z);
    const exp = Array.from(z, (v) => Math.exp(v - max));
    const total = exp.reduce((s, v) => s + v, 0);
    let best = 0;
    for (let i = 1; i < 10; i++) if (exp[i] > exp[best]) best = i;
    return { label: String(best), probability: exp[best] / total };
  }

  // ---------- Erkennen ----------

  // → Promise { text, chars: [{ label, probability, strokes }], unsure }; „?“ für nicht lesbare Zeichen
  async function recognize(strokes) {
    await load();
    const chars = segment(strokes).map((g) => {
      if (g.comma) return { label: ",", probability: 1, strokes: g.strokes };
      if (!weights) return { label: "?", probability: 0, strokes: g.strokes };
      const r = classify(g.strokes);
      return { label: r.probability >= UNSURE_PROBABILITY ? r.label : "?", probability: r.probability, strokes: g.strokes };
    });
    return { text: chars.map((c) => c.label).join(""), chars, unsure: chars.some((c) => c.label === "?") };
  }

  // Bestätigte Ziffer zum Speichern: Striche auf das Kästchen der Ziffer bezogen (Höhe = 1)
  function toStored(label, strokes) {
    const b = box(strokes.flatMap((s) => s.points));
    const size = Math.max(b.h, b.w, 1e-6);
    return { label, strokes: strokes.map((s) => s.points.slice(0, 200).map((p) => [+((p.x - b.minX) / size).toFixed(3), +((p.y - b.minY) / size).toFixed(3)])) };
  }

  return { recognize, segment, toStored, load, renderChar, logits: (img) => (weights ? logits(img) : null), SHAPES };
})();
