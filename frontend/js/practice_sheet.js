// ==========================================================================
// Übungsblatt für die Tafel (Tafel-Stufen 1–4 einer Sachaufgabe)
// --------------------------------------------------------------------------
// Zeichnet die Aufgabe wie ein bedrucktes Blatt (durchsichtig, das Tafel-Gitter
// scheint durch) und liefert es als Bild für die Unterlage der Tafel. Das Gerüst
// nimmt mit der Stufe ab (Konzept-Doc, Steckbrief Typ 1):
//   1 Tabelle mit Kopf, Startzeile und Zielwert, Antwortsatz angefangen
//   2 nur Tabellenkopf bzw. „Überschlag:“, „R:“, „A:“
//   3 nur „R:“ und „A:“
//   4 nur die Aufgabe, wie im Test
// Mit solution = true schreibt Luna die Lösung in ihrer Farbe hinein.
// Feste Breite: Theas Striche liegen in festen Koordinaten, das Blatt darf sich
// beim Drehen des iPads nicht unter der Schrift verschieben.
// ==========================================================================

const PRACTICE_SHEET_WIDTH = 780;

// Versuch festhalten (Lernstand; genutzt vom Tab „Üben“ und von der Übungstafel). Liefert ein Promise
// auf den Versuch; schlägt das Melden fehl, übt Thea trotzdem weiter.
function startPracticeAttempt(exerciseId, stage, boardId = null) {
  return apiJson(`/api/v1/practice/${encodeURIComponent(exerciseId)}/attempts`, {
    method: "POST",
    json: { stage, board_id: boardId },
  }).catch((err) => {
    console.warn("Übungsversuch nicht angelegt:", err);
    return null;
  });
}

// Ereignis zum Versuch melden: 'guess' {value}, 'hint', 'solution', 'check' {status, …} (nur Stufe 0)
function logPracticeEvent(attemptPromise, kind, data = {}) {
  if (!attemptPromise) return;
  attemptPromise
    .then((attempt) => attempt && apiJson(`/api/v1/practice/attempts/${encodeURIComponent(attempt.id)}/events`, {
      method: "POST",
      json: { kind, data },
    }))
    .catch((err) => console.warn("Übungsereignis nicht gemeldet:", err));
}

// Name der Übungstafel, z. B. „S. 27 Nr. 3c · Stufe 2“ (Zwillinge: „(ähnlich)“)
function practiceBoardTitle(quelle, ableitung, stage) {
  const src = quelle.art === "Buch" ? `S. ${quelle.seite} Nr. ${quelle.nummer}` : `${quelle.material} Nr. ${quelle.nummer}`;
  const suffix = `${ableitung === "B" ? " (ähnlich)" : ""} · Stufe ${stage}`;
  return (src.slice(0, 60 - suffix.length) + suffix).trim();
}

function renderPracticeSheet(ex, stage, { light = false, solution = false } = {}) {
  const W = PRACTICE_SHEET_WIDTH;
  const dpr = 2;
  const font = '-apple-system, "Helvetica Neue", Arial, sans-serif';
  const ink = light ? "#1b2130" : "#e8eaf2";
  const faint = light ? "rgba(27, 33, 48, 0.55)" : "rgba(232, 234, 242, 0.5)";
  const rule = light ? "rgba(27, 33, 48, 0.4)" : "rgba(232, 234, 242, 0.38)";
  const luna = light ? "#b45309" : "#f2b84b";
  const pad = 36;
  const right = W - pad;

  const draft = document.createElement("canvas");
  draft.width = W * dpr;
  draft.height = 2600 * dpr;
  const ctx = draft.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.textBaseline = "alphabetic";

  const fmt = (x, unit) => {
    const n = Number(x);
    if (unit === "€" && !Number.isInteger(n)) return n.toFixed(2).replace(".", ",");
    return String(n).replace(".", ",");
  };
  const setFont = (size, weight = 400, style = "") => { ctx.font = `${style} ${weight} ${size}px ${font}`.trim(); };
  const wrap = (text, maxWidth) => {
    const lines = [];
    let line = "";
    String(text).split(/\s+/).forEach((word) => {
      const test = line ? `${line} ${word}` : word;
      if (ctx.measureText(test).width > maxWidth && line) {
        lines.push(line);
        line = word;
      } else {
        line = test;
      }
    });
    if (line) lines.push(line);
    return lines;
  };
  const text = (t, x, y, color = ink) => { ctx.fillStyle = color; ctx.fillText(t, x, y); return x + ctx.measureText(t).width; };
  const label = (t, x, y) => { setFont(21, 700); return text(t, x, y) + 10; };
  const hline = (x1, x2, y) => {
    ctx.strokeStyle = rule;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(x1, y);
    ctx.lineTo(x2, y);
    ctx.stroke();
  };
  // Lunas Schrift: kräftig, kursiv, in ihrer Farbe
  const lunaWrite = (t, x, y, maxWidth, lineGap = 46) => {
    setFont(22, 600, "italic");
    wrap(t, maxWidth).forEach((l, i) => text(l, x, y + i * lineGap, luna));
  };

  let y = 34;
  const q = ex.quelle;
  setFont(14);
  text(`${q.material}${q.seite ? `, S. ${q.seite}` : ""}, Nr. ${q.nummer}${ex.ableitung === "B" ? " · ähnliche Aufgabe" : ""}`, pad, y, faint);
  y += 38;
  setFont(23);
  wrap(ex.aufgabentext, right - pad).forEach((l) => { text(l, pad, y); y += 33; });
  y += 30;

  // Begründung (falls die Aufgabe eine verlangt)
  if (ex.begruendung && ex.begruendung.verlangt && stage <= 3) {
    const x = label("Begründung:", pad, y);
    hline(x, right, y + 8);
    hline(pad, right, y + 54);
    if (solution) lunaWrite(ex.begruendung.erwartung, x + 4, y, right - x - 8);
    y += 104;
  }

  // Überschlag (falls verlangt)
  if (ex.ueberschlag && ex.ueberschlag.verlangt && stage <= 2) {
    let x = label("Überschlag:", pad, y);
    if (stage === 1) {
      setFont(22);
      x = text(`${ex.ueberschlag.ausdruck.split("=")[0].trim()} = `, x, y) + 6;
      hline(x, x + 150, y + 8);
      if (solution) lunaWrite(`${ex.ueberschlag.ausdruck.split("=")[1].trim()}  → ${ex.ueberschlag.folgerung}`, x + 6, y, right - x);
    } else {
      hline(x, right, y + 8);
      if (solution) lunaWrite(`${ex.ueberschlag.ausdruck} → ${ex.ueberschlag.folgerung}`, x + 6, y, right - x);
    }
    y += 76;
  }

  // Rechnung
  if (stage <= 3) label("R:", pad, y);
  if (ex.schema === "rechnung") {
    if (stage === 1) {
      const [a, b] = ex.rechnung.ausdruck.split(":").map((t) => t.trim());
      const [ua, ub] = ex.rechnung.umformung.split(":").map((t) => t.trim());
      setFont(22);
      let x = text(`${a} : ${b} = `, pad + 40, y) + 4;
      const blank = (w, value) => {
        hline(x, x + w, y + 8);
        if (solution) { setFont(22, 600, "italic"); text(value, x + 8, y, luna); setFont(22); }
        x += w + 6;
      };
      blank(130, ua);
      x = text(" : ", x, y) + 4;
      blank(90, ub);
      x = text(" = ", x, y) + 4;
      blank(140, fmt(ex.ergebnis.wert));
      y += 84;
    } else if (stage <= 3 || solution) {
      if (solution) lunaWrite(`${ex.rechnung.ausdruck} = ${ex.rechnung.umformung} = ${fmt(ex.ergebnis.wert)}`, pad + 40, y, right - pad - 40);
      y += 220;
    }
  } else if (stage <= 2 || solution) {
    y = drawRuleOfThree(y + 18, stage <= 2 ? stage : 2);
  } else {
    y += 300;
  }

  // Antwortsatz
  if (stage <= 3) {
    let x = label("A:", pad, y);
    let rest = ex.antwortsatz;
    if (stage === 1) {
      setFont(22);
      x = text(ex.antwort_anfang, x, y) + 8;
      rest = ex.antwortsatz.slice(ex.antwort_anfang.length).trim();
    }
    hline(x, right, y + 8);
    if (solution) lunaWrite(rest, x + 6, y, right - x - 6);
    y += 60;
  } else if (solution) {
    lunaWrite(`A: ${ex.antwortsatz}`, pad, y, right - pad);
    y += 60;
  }
  y += 320;  // Platz zum Schreiben unter dem Blatt

  const out = document.createElement("canvas");
  out.width = W * dpr;
  out.height = Math.ceil(y * dpr);
  out.getContext("2d").drawImage(draft, 0, 0);
  return out.toDataURL("image/png");

  // Dreisatz-Tabelle wie im Buch: Rechenschritte links und rechts, Pfeile nach unten
  function drawRuleOfThree(top, tableStage) {
    const [g1, g2] = ex.groessen;
    const anti = ex.schema === "dreisatz_antiproportional";
    const inv = (op) => (op[0] === ":" ? "·" : ":") + op.slice(1);
    const opsL = ex.schritte;
    const opsR = anti ? opsL.map(inv) : opsL;
    const money = g2.einheit === "€";
    const opW = 120, colW = 190, valH = 64, opH = 54;
    const xL = pad + 24, c1 = xL + opW, c2 = c1 + colW, xR = c2 + colW;
    const head = (g) => g.name + (g.einheit ? ` (in ${g.einheit})` : "");

    setFont(18);
    ctx.textAlign = "center";
    text(head(g1), c1 + colW / 2, top + 22);
    text(head(g2), c2 + colW / 2, top + 22);
    ctx.textAlign = "left";
    const headLine = top + 34;
    hline(c1 + 10, xR - 10, headLine);

    let cy = headLine;
    const rows = [];
    ex.zeilen.forEach((row, i) => {
      rows.push({ kind: "val", i, top: cy });
      cy += valH;
      if (i < opsL.length) { rows.push({ kind: "op", i, top: cy }); cy += opH; }
    });
    // Trennstrich zwischen den Spalten
    ctx.strokeStyle = rule;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(c2, headLine);
    ctx.lineTo(c2, cy - 8);
    ctx.stroke();

    const cell = (value, cx, rowTop, printed) => {
      const base = rowTop + valH / 2 + 10;
      ctx.textAlign = "center";
      if (printed) {
        setFont(22);
        text(value, cx, base);
      } else {
        if (tableStage === 1) hline(cx - 60, cx + 60, base + 8);
        if (solution) { setFont(22, 600, "italic"); text(value, cx, base, luna); }
      }
      ctx.textAlign = "left";
    };
    const opBox = (op, x, rowTop, arrowLeft) => {
      const bx = x, by = rowTop + 10, bw = 72, bh = 42;
      if (tableStage === 1) {
        ctx.strokeStyle = rule;
        ctx.lineWidth = 2;
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(bx, by, bw, bh, 8);
        else ctx.rect(bx, by, bw, bh);
        ctx.stroke();
      }
      setFont(20);
      text("↓", arrowLeft ? bx + bw + 8 : bx - 22, by + 30, faint);
      if (solution) {
        setFont(22, 600, "italic");
        ctx.textAlign = "center";
        text(op, bx + bw / 2, by + 30, luna);
        ctx.textAlign = "left";
      }
    };

    rows.forEach((r) => {
      if (r.kind === "val") {
        const [xv, yv] = ex.zeilen[r.i];
        const last = r.i === ex.zeilen.length - 1;
        cell(fmt(xv), c1 + colW / 2, r.top, tableStage === 1 && (r.i === 0 || last));
        cell(fmt(yv, money ? "€" : ""), c2 + colW / 2, r.top, tableStage === 1 && r.i === 0);
      } else {
        opBox(opsL[r.i], xL - 16, r.top, true);
        opBox(opsR[r.i], xR + 24, r.top, false);
      }
    });
    return cy + 46;
  }
}
