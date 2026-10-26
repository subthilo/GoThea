// ============================================================================
// Bemalbare Flächen (Malen – Architektur): welche Seiten und Kacheln Thea bemalen kann
// ============================================================================
// Eine Seite (Tab) weist sich mit data-paint="<Platz>" aus, z. B. "dashboard" oder "subject-detail/sub_math".
// Eine Kachel darauf mit data-paint-tile="<Name>" und data-paint-kind="<Kachelart>"; ihr Platz ist
// "<Seite>/tile/<Name>", z. B. "dashboard/tile/sub_math". Namen sind stabil (Fach-ID oder fester Name,
// nie die Position in einer Liste). Jeder Platz zeigt nur sein eigenes Bild.
// Jede Kachelart hat ein festes Seitenverhältnis; passt die Kachel gerade nicht genau (andere Lage,
// anderes Gerät), wird das Bild mittig beschnitten. tests/unit/test_paint_slots.py prüft die Arten.

const PAINT_TILE_KINDS = {
  quadrat: { aspect: 1 },    // Fach-Kacheln der Startseite
  band: { aspect: 6 },       // Stundenplan-Karte, Kopfkarte der Fachseite
  karte: { aspect: 2.4 },    // Aktionskarten der Fachseite (Tafel, Üben, Upload)
};

// Bemalbare Kacheln der aktiven Seite (sichtbar, mit bekannter Art)
function paintTilesOf(pane) {
  if (!pane || !pane.dataset.paint) return [];
  return [...pane.querySelectorAll("[data-paint-tile]")]
    .filter((el) => PAINT_TILE_KINDS[el.dataset.paintKind] && el.getClientRects().length > 0)
    .map((el) => ({ el, kind: el.dataset.paintKind, key: `${pane.dataset.paint}/tile/${el.dataset.paintTile}` }));
}
