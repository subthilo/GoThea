// ==========================================================================
// Ziffern aus Pencil-Strichen erkennen (Schreibfeld der Stufe „Gedankengang“)
// --------------------------------------------------------------------------
// Ohne KI und ohne Wartezeit, direkt im Browser:
//   1. segment(): Striche nach links/rechts zu Zeichen gruppieren (überlappende
//      Striche gehören zusammen, z. B. die zwei Striche einer 4); ein kleiner
//      Strich unten ist ein Komma.
//   2. classify(): jedes Zeichen mit dem $P-Punktwolken-Erkenner (Vatavu, Anthony,
//      Wobbrock 2012) gegen Muster vergleichen. Strichreihenfolge und -richtung
//      spielen keine Rolle. Mitgeliefert sind gezeichnete Musterziffern; dazu
//      kommen Theas eigene Ziffern, sobald sie bestätigt sind (personal samples).
// Striche im Format des Zeichenkerns: { points: [{ x, y }, …] }.
// ==========================================================================

const DigitInk = (function () {
  const N = 32;                 // Punkte je Zeichen nach dem Neuabtasten
  const UNSURE_DISTANCE = 2.6;  // schlechter als das: Zeichen gilt als nicht lesbar (gemessen: echte Ziffern < ~2)
  const LABELS = "0123456789";

  // ---------- $P: Punktwolke vorbereiten und vergleichen ----------

  function flatten(strokes) {
    const pts = [];
    strokes.forEach((s, id) => s.points.forEach((p) => pts.push({ x: p.x, y: p.y, id })));
    return pts;
  }

  function pathLength(pts) {
    let d = 0;
    for (let i = 1; i < pts.length; i++) {
      if (pts[i].id === pts[i - 1].id) d += Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y);
    }
    return d;
  }

  function resample(input, n) {
    const pts = input.map((p) => ({ ...p }));
    const I = pathLength(pts) / (n - 1);
    if (!I) return Array.from({ length: n }, () => ({ ...pts[0] }));
    let D = 0;
    const out = [{ ...pts[0] }];
    for (let i = 1; i < pts.length; i++) {
      if (pts[i].id !== pts[i - 1].id) continue;
      const d = Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y);
      if (D + d >= I) {
        const t = (I - D) / d;
        const q = { x: pts[i - 1].x + t * (pts[i].x - pts[i - 1].x), y: pts[i - 1].y + t * (pts[i].y - pts[i - 1].y), id: pts[i].id };
        out.push(q);
        pts.splice(i, 0, q);
        D = 0;
      } else {
        D += d;
      }
    }
    while (out.length < n) out.push({ ...pts[pts.length - 1] });
    return out.slice(0, n);
  }

  function normalize(points) {
    let pts = resample(points, N);
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    pts.forEach((p) => { minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x); minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y); });
    const size = Math.max(maxX - minX, maxY - minY) || 1;
    pts = pts.map((p) => ({ x: (p.x - minX) / size, y: (p.y - minY) / size, id: p.id }));
    const cx = pts.reduce((s, p) => s + p.x, 0) / N, cy = pts.reduce((s, p) => s + p.y, 0) / N;
    return pts.map((p) => ({ x: p.x - cx, y: p.y - cy, id: p.id }));
  }

  function cloudDistance(a, b, start) {
    const matched = new Array(N).fill(false);
    let sum = 0, i = start;
    do {
      let min = Infinity, index = -1;
      for (let j = 0; j < N; j++) {
        if (matched[j]) continue;
        const d = Math.hypot(a[i].x - b[j].x, a[i].y - b[j].y);
        if (d < min) { min = d; index = j; }
      }
      matched[index] = true;
      const weight = 1 - ((i - start + N) % N) / N;
      sum += weight * min;
      i = (i + 1) % N;
    } while (i !== start);
    return sum;
  }

  function greedyMatch(a, b) {
    const step = Math.floor(Math.pow(N, 0.5));
    let min = Infinity;
    for (let i = 0; i < N; i += step) {
      min = Math.min(min, cloudDistance(a, b, i), cloudDistance(b, a, i));
    }
    return min;
  }

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

  // Gezeichnet im Einheitsquadrat; echte Ziffern sind schmaler als hoch (der Vergleich behält das Seitenverhältnis)
  const DIGIT_ASPECT = 0.62;
  const narrow = (strokes) => strokes.map((s) => ({ points: s.points.map((p) => ({ x: p.x * DIGIT_ASPECT, y: p.y })) }));
  const BUILTIN = [];
  Object.entries(SHAPES).forEach(([label, variants]) =>
    variants.forEach((strokes) => BUILTIN.push({ label, cloud: normalize(flatten(narrow(strokes))), builtin: true })));

  // Eigene Muster: { label, points: [[x, y, id], …] } (bereits normalisiert gespeichert)
  function fromStored(samples) {
    return (samples || [])
      .filter((s) => LABELS.includes(s.label) && Array.isArray(s.points) && s.points.length === N)
      .map((s) => ({ label: s.label, cloud: s.points.map(([x, y, id]) => ({ x, y, id })) }));
  }
  function toStored(label, strokes) {
    return { label, points: normalize(flatten(strokes)).map((p) => [+p.x.toFixed(4), +p.y.toFixed(4), p.id]) };
  }

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
      const comma = isComma(item.box);
      const last = groups[groups.length - 1];
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

  // ---------- Erkennen ----------

  function classify(strokes, personal) {
    const cloud = normalize(flatten(strokes));
    let best = null;
    for (const t of [...BUILTIN, ...personal]) {
      const d = greedyMatch(cloud, t.cloud);
      if (!best || d < best.distance) best = { label: t.label, distance: d };
    }
    return best;
  }

  // → { text, chars: [{ label, distance, strokes }], unsure }; „?“ für nicht lesbare Zeichen
  function recognize(strokes, storedSamples) {
    const personal = fromStored(storedSamples);
    const chars = segment(strokes).map((g) => {
      if (g.comma) return { label: ",", distance: 0, strokes: g.strokes };
      const r = classify(g.strokes, personal);
      return { label: r.distance <= UNSURE_DISTANCE ? r.label : "?", distance: r.distance, strokes: g.strokes };
    });
    return { text: chars.map((c) => c.label).join(""), chars, unsure: chars.some((c) => c.label === "?") };
  }

  return { recognize, segment, toStored, SHAPES, N };
})();
