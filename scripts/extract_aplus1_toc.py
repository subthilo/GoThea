import json
import re
from backend.app.config import OPENAI_API_KEY
from openai import OpenAI
from backend.app.services.material_ingestion import render_material_page_as_image, prepare_image_base64_for_vision

client = OpenAI(api_key=OPENAI_API_KEY)

user_content = [
    {
        "type": "text", 
        "text": """Hier sind die Seiten 4 bis 9 des Inhaltsverzeichnisses des Französisch-Lehrwerks 'À plus! 1' (Gymnasium, Cornelsen Verlag, Gesamtseitenzahl im PDF 226). 
Bitte extrahiere das komplette Lehrwerk inklusive aller Hauptkapitel:
- Einstieg ('C est parti !' ca. Buchseite 8-15)
- Unité 1 bis Unité 6
- Anhang (Grammatik / Vocabulaire / Dictionnaire falls aufgeführt)
Für jedes Kapitel: unit_number, title, book_start_page, book_end_page, topic_name, focus, und sections (mit title, book_page, level).
Antworte AUSSCHLIESSLICH als JSON im Format:
{
  "chapters": [
    {
      "unit_number": 0,
      "title": "C'est parti ! (Einstieg)",
      "book_start_page": 8,
      "book_end_page": 15,
      "topic_name": "Französisch Grundlagen",
      "focus": "Erste Kontakte, Begrüßung und Zahlen",
      "sections": [{"title": "1. Bonjour!", "book_page": 8, "level": 2}]
    }
  ]
}"""
    }
]

print("Rendering pages 4 to 9...")
for p in range(4, 10):
    img_bytes, mime = render_material_page_as_image("/home/pi/GoThea/data/staging/materials/mat_788ac7bd.pdf", "application/pdf", page_num=p)
    b64 = prepare_image_base64_for_vision(img_bytes, mime)
    user_content.append({
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}
    })

print("Calling OpenAI GPT-4o-mini...")
resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "Du bist ein präziser Experte für französische Schulbücher. Gib ausschließlich valides JSON aus."},
        {"role": "user", "content": user_content}
    ],
    temperature=0.1,
    max_tokens=4000
)

raw = resp.choices[0].message.content.strip()
raw = re.sub(r"^```json\s*", "", raw)
raw = re.sub(r"^```\s*", "", raw)
raw = re.sub(r"\s*```$", "", raw)

data = json.loads(raw)
with open("/tmp/aplus1_toc.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"Successfully extracted {len(data.get('chapters', []))} chapters to /tmp/aplus1_toc.json")
for c in data.get('chapters', []):
    print(f"  - {c.get('title')} (p.{c.get('book_start_page')}-{c.get('book_end_page')}), sections: {len(c.get('sections', []))}")
