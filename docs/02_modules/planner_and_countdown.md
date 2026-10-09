# 02.2 Lernplan- & Countdown-Engine (Deterministisch)

## 1. Mathematische Modellierung & Alterskalibrierung

Für jeden Prüfungstermin $T$ mit Prüfungsdatum $d(T)$, Art $k(T) \in \{\text{Test}, \text{Klassenarbeit}, \text{Klausur}\}$ und Klassenstufe $g \in \{1, \dots, 13\}$ berechnet die Engine deterministisch:

### Vorbereitungsfenster $N(k, g)$ in Tagen:
$$
N(k, g) = \begin{cases} 
3 \text{ bis } 4 \text{ Tage}, & \text{wenn } k = \text{Test} \land g \le 4 \\
5 \text{ Tage}, & \text{wenn } k = \text{Test} \land g \in \{5, \dots, 9\} \\
7 \text{ Tage}, & \text{wenn } k = \text{Test} \land g \ge 10 \\
7 \text{ Tage}, & \text{wenn } k = \text{Klassenarbeit} \land g \le 4 \\
10 \text{ Tage}, & \text{wenn } k = \text{Klassenarbeit} \land g \in \{5, \dots, 9\} \\
14 \text{ Tage}, & \text{wenn } k = \text{Klausur} \land g \ge 10 
\end{cases}
$$

### Tägliches Richt-Zeitbudget $B(k, g)$ in Minuten:
$$
B(k, g) = \begin{cases}
10 \text{ bis } 15 \text{ Min.}, & \text{wenn } g \le 4 \\
20 \text{ Min.}, & \text{wenn } k = \text{Test} \land g \in \{5, \dots, 9\} \\
25 \text{ Min.}, & \text{wenn } k = \text{Klassenarbeit} \land g \in \{5, \dots, 9\} \\
35 \text{ bis } 45 \text{ Min.}, & \text{wenn } g \ge 10 \text{ (Oberstufe)}
\end{cases}
$$

---

## 2. Phasenallokation

Sei $C = \{c_1, c_2, \dots, c_m\}$ die chronologische Menge verfügbarer Lerntage vor $d(T)$ (abzüglich Sperrtage):

1. **Phase 1 – Grundlagen & Verstehen:** Tage $c_i$ mit $i \le \lfloor 0{,}4 \cdot m \rfloor$.
   * Fokus: Wissenslücken schließen, Zusammenfassungen durchgehen.
2. **Phase 2 – Aktives Üben & Vertiefen:** Tage $c_i$ mit $\lfloor 0{,}4 \cdot m \rfloor < i < m$.
   * Fokus: Standardaufgaben, eigenständiges Rechnen auf der Tafel.
3. **Phase 3 – Letzte Runde (Generalprobe):** Tag $c_m$ (letzter Tag vor Prüfung).
   * Fokus: Zeitgestoppte Musteraufgabe, mentale Stärkung.
4. **Prüfungstag $d(T)$:** Ruhemodus (*„Heute musst du nicht mehr lernen. Du bist vorbereitet!“*).
