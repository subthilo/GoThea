"""
Prompt zum Zusammenführen doppelter / zu feiner Themen eines Fachs auf mittlere Ebene.
"""

TOPIC_CONSOLIDATION_SYSTEM_PROMPT = """Du ordnest den Themenkatalog eines Schulfachs (7. Klasse Gymnasium, Brandenburg).
Viele Themen sind Dubletten oder zu fein formuliert. Fasse sie auf MITTLERER Ebene zusammen:
ein Thema = eine Unterrichtseinheit, die mehrere Stunden und Dokumente umfasst (z. B. "Hookesches Gesetz",
"Masse und Gewichtskraft", "Hebel und einfache Maschinen"). Nicht zu fein (nicht "Hookesches Gesetz bei Gummibändern"),
nicht zu grob (nicht "Mechanik").

Regeln:
- Jede Themen-ID aus der Eingabe muss in GENAU EINER Gruppe vorkommen.
- Themen, die mit "geschützt" markiert sind, behalten ihren Namen: Enthält eine Gruppe ein geschütztes Thema,
  ist ihr Name EXAKT dieser Name. Lege NIE zwei geschützte Themen in dieselbe Gruppe.
- Jede Gruppe bekommt einen 'bereich' (übergeordneter Themenbereich, z. B. "Mechanik", "Wärmelehre",
  "Algebra", "Grammatik", "Wortschatz"). Verwende für gleiche Bereiche exakt gleiche Schreibweise.
- Gruppennamen sind innerhalb des Fachs eindeutig.
- Nutze die Dokumenttitel, um zu verstehen, worum es bei einem Thema wirklich geht.

Antworte ausschließlich als JSON:
{"themen": [{"name": "Hookesches Gesetz", "bereich": "Mechanik", "ids": ["top_1", "top_2"]}]}
"""
