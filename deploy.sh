#!/bin/bash
set -e

# Parameter & Optionen auswerten
TARGET_ENV="all"
SKIP_TESTS=0
INSTALL_DEPS=0
QUICK_FRONTEND=0

for arg in "$@"; do
    case "$arg" in
        prod|staging|all)
            TARGET_ENV="$arg"
            ;;
        --skip-tests|--no-tests|-n)
            SKIP_TESTS=1
            ;;
        --deps|-d)
            INSTALL_DEPS=1
            ;;
        --frontend|-f|quick)
            QUICK_FRONTEND=1
            ;;
        *)
            echo "Unbekannter Parameter: $arg"
            echo "Verwendung: ./deploy.sh [prod|staging|all] [--skip-tests|-n] [--frontend|-f] [--deps|-d]"
            exit 1
            ;;
    esac
done

if [ "$ENV_SKIP_TESTS" = "1" ]; then
    SKIP_TESTS=1
fi

PI_USER="pi"
PI_HOST="192.168.1.135"
REMOTE_DIR="/home/$PI_USER/GoThea"

# Schneller Frontend-Sync (nur statische Dateien kopieren, keine Tests, kein Service-Neustart)
if [ "$QUICK_FRONTEND" -eq 1 ]; then
    echo "⚡ [Frontend-Deploy] Synchronisiere 'frontend/' mit Pi ($PI_HOST)..."
    rsync -avz ./frontend/ "$PI_USER@$PI_HOST:$REMOTE_DIR/frontend/"
    echo "✅ Frontend blitzschnell synchronisiert! (Kein Service-Restart nötig)"
    exit 0
fi

# 1. Tests ausführen (falls nicht übersprungen)
if [ "$SKIP_TESTS" -eq 1 ]; then
    echo "⚡ [1/4] Tests übersprungen (--skip-tests)."
else
    echo "🧪 [1/4] Führe lokale Testsuite aus (-q für kompakte Ausgabe)..."
    if [ -d ".venv" ]; then
        .venv/bin/pytest -q
    else
        pytest -q
    fi
    echo "✅ Alle Tests erfolgreich bestanden!"
fi

# 2. Synchronisieren
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
  --exclude 'experiments/' \
  --exclude 'inbox/' \
  --exclude '.env' \
  --exclude '.requirements.md5' \
  ./ "$PI_USER@$PI_HOST:$REMOTE_DIR/"

# 3. Services auf dem Pi konfigurieren
echo "⚙️  [3/4] Konfiguriere Services auf dem Pi für Target: $TARGET_ENV..."
ssh "$PI_USER@$PI_HOST" bash -s "$TARGET_ENV" "$INSTALL_DEPS" << 'EOF'
set -e
TARGET="$1"
INSTALL_DEPS="$2"
cd /home/pi/GoThea

# 1. Virtual Environment einrichten falls nötig
if [ ! -d ".venv" ]; then
    echo "📦 Erstelle Python Virtual Environment (.venv)..."
    python3 -m venv .venv
    INSTALL_DEPS=1
fi

# 2. Dependencies installieren nur wenn nötig oder erzwungen
CURRENT_REQ_HASH=$(md5sum backend/requirements.txt | awk '{print $1}')
STORED_REQ_HASH=""
if [ -f ".requirements.md5" ]; then
    STORED_REQ_HASH=$(cat .requirements.md5)
fi

if [ "$INSTALL_DEPS" = "1" ] || [ "$CURRENT_REQ_HASH" != "$STORED_REQ_HASH" ]; then
    echo "📦 Aktualisiere Abhängigkeiten auf dem Pi..."
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet -r backend/requirements.txt
    echo "$CURRENT_REQ_HASH" > .requirements.md5
else
    echo "⚡ Python-Abhängigkeiten unverändert (Überspringe pip install)."
fi

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
