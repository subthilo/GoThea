# 03.2 WebSocket Protokoll

Endpunkt: `/ws/tutor/{session_id}` bzw. `/ws`

---

## 1. Client $\rightarrow$ Server Nachrichten

### `canvas_update`
Übermittelt neue Vektorstriche oder Snapshot-Diffs vom iPad:
```json
{
  "type": "canvas_update",
  "strokes": [
    {
      "points": [{"x": 120, "y": 340, "pressure": 0.8}],
      "color": "#ffffff",
      "width": 3
    }
  ],
  "timestamp": 1773294821
}
```

### `user_interrupt`
Barge-In Event (Schüler fängt an zu schreiben/sprechen während die KI spricht):
```json
{
  "type": "user_interrupt",
  "reason": "pencil_touch"
}
```

---

## 2. Server $\rightarrow$ Client Nachrichten

### `board_actions`
Visuelle Rückmeldung der KI auf dem Whiteboard-Overlay:
```json
{
  "type": "board_actions",
  "actions": [
    {
      "action": "highlight_box",
      "coords": {"x": 100, "y": 320, "w": 250, "h": 60},
      "color": "#f59e0b"
    },
    {
      "action": "latex_hint",
      "latex": "-(a + b) = -a - b",
      "position": {"x": 380, "y": 340}
    }
  ]
}
```

### `audio_chunk`
Gekoppeltes Streaming-Audio (Base64 oder binäre Chunks):
```json
{
  "type": "audio_chunk",
  "chunk_index": 1,
  "data": "GkXfo59ChoEBQveBAULygQ8t..."
}
```
