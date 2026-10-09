#!/bin/bash
set -e

PI_USER="pi"
PI_HOST="192.168.1.135"
REMOTE_DIR="/home/$PI_USER/GoThea"

echo "🧪 [1/4] Führe lokale Testsuite aus..."
if [ -d ".venv" ]; then
    .venv/bin/pytest -v
else
    pytest -v
fi
echo "✅ Alle Tests erfolgreich bestanden!"

echo "🚀 [2/4] Synchronisiere Code mit Raspberry Pi ($PI_HOST)..."
rsync -avz --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.pytest_cache' \
  --exclude '.coverage' \
  --exclude '.DS_Store' \
  --exclude 'data/' \
  ./ "$PI_USER@$PI_HOST:$REMOTE_DIR/"

echo "⚙️  [3/4] Konfiguriere Umgebung & Service auf dem Pi..."
ssh "$PI_USER@$PI_HOST" bash << 'EOF'
set -e
cd /home/pi/GoThea

# 1. Virtual Environment einrichten falls nötig
if [ ! -d ".venv" ]; then
    echo "📦 Erstelle Python Virtual Environment (.venv)..."
    python3 -m venv .venv
fi

# 2. Dependencies installieren / aktualisieren
echo "📦 Installiere Abhängigkeiten..."
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r backend/requirements.txt

# 3. Systemd Service einrichten & neustarten
if [ -f "gothea.service" ]; then
    sudo cp gothea.service /etc/systemd/system/gothea.service
    sudo systemctl daemon-reload
    sudo systemctl enable gothea.service
    sudo systemctl restart gothea.service
    echo "🔄 Service 'gothea' neu gestartet."
fi
EOF

echo "✅ [4/4] Deployment abgeschlossen!"
echo "👉 Auf dem iPad im Browser aufrufen: http://$PI_HOST:8000"
