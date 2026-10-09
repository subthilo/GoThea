#!/bin/bash
set -e

TARGET_ENV="${1:-all}"  # "staging", "prod" oder "all" (default)
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

echo "⚙️  [3/4] Konfiguriere Services auf dem Pi für Target: $TARGET_ENV..."
ssh "$PI_USER@$PI_HOST" bash -s "$TARGET_ENV" << 'EOF'
set -e
TARGET="$1"
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

# Verzeichnisse für getrennte Datenbanken anlegen
mkdir -p data/prod data/staging

# 3. Systemd Services aktualisieren
sudo cp gothea.service /etc/systemd/system/gothea.service
sudo cp gothea-staging.service /etc/systemd/system/gothea-staging.service
sudo systemctl daemon-reload
sudo systemctl enable gothea.service gothea-staging.service

if [ "$TARGET" == "staging" ]; then
    sudo systemctl restart gothea-staging.service
    echo "🔄 Service 'gothea-staging' (Port 8001) neu gestartet."
elif [ "$TARGET" == "prod" ]; then
    sudo systemctl restart gothea.service
    echo "🔄 Service 'gothea' (Port 8000) neu gestartet."
else
    sudo systemctl restart gothea.service
    sudo systemctl restart gothea-staging.service
    echo "🔄 Beide Services (Port 8000 & 8001) neu gestartet."
fi
EOF

echo "✅ [4/4] Deployment abgeschlossen!"
echo "👉 🟢 PRODUKTION (geschützte Daten): http://$PI_HOST:8000"
echo "👉 🟡 STAGING    (Test-Spielwiese):  http://$PI_HOST:8001"
