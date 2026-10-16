#!/bin/bash
set -e

# Staging und Produktion haben auf dem Pi je einen eigenen Code-Ordner:
#   staging -> /home/pi/GoThea-staging (Port 8001)   prod -> /home/pi/GoThea (Port 8000)
# Standard ist staging: Neues erreicht Thea erst mit einem ausdrücklichen "prod" oder "all".

# Parameter & Optionen auswerten
TARGET_ENV="staging"
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
            echo "Verwendung: ./deploy.sh [staging|prod|all] [--skip-tests|-n] [--frontend|-f] [--deps|-d]"
            exit 1
            ;;
    esac
done

if [ "$ENV_SKIP_TESTS" = "1" ]; then
    SKIP_TESTS=1
fi

PI_USER="pi"
# Zuhause WLAN-Adresse, unterwegs Tailscale (PI_HOST=… erzwingt einen Weg)
source "$(dirname "$0")/scripts/pi_host.sh"
echo "📡 Pi erreichbar über $PI_HOST"

case "$TARGET_ENV" in
    staging) TARGETS="staging" ;;
    prod)    TARGETS="prod" ;;
    all)     TARGETS="staging prod" ;;
esac

remote_dir() { [ "$1" = "prod" ] && echo "/home/$PI_USER/GoThea" || echo "/home/$PI_USER/GoThea-staging"; }
service_name() { [ "$1" = "prod" ] && echo "gothea" || echo "gothea-staging"; }
service_port() { [ "$1" = "prod" ] && echo "8000" || echo "8001"; }

# Schneller Frontend-Sync (nur statische Dateien kopieren, keine Tests, kein Service-Neustart)
if [ "$QUICK_FRONTEND" -eq 1 ]; then
    for t in $TARGETS; do
        echo "⚡ [Frontend-Deploy → $t] Synchronisiere 'frontend/' nach $(remote_dir "$t")..."
        rsync -avz ./frontend/ "$PI_USER@$PI_HOST:$(remote_dir "$t")/frontend/"
    done
    echo "✅ Frontend synchronisiert ($TARGET_ENV, kein Service-Restart nötig)"
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

for t in $TARGETS; do
    DIR="$(remote_dir "$t")"
    SERVICE="$(service_name "$t")"
    PORT="$(service_port "$t")"

    # 2. Synchronisieren
    echo "🚀 [2/4 → $t] Synchronisiere Code nach $DIR..."
    rsync -avz --delete \
      --exclude '.git' \
      --exclude '.venv' \
      --exclude '__pycache__' \
      --exclude '*.pyc' \
      --exclude '.pytest_cache' \
      --exclude '.ruff_cache' \
      --exclude '.coverage' \
      --exclude '.DS_Store' \
      --exclude '/data' \
      --exclude '/data/**' \
      --exclude '/experiments' \
      --exclude '/experiments/**' \
      --exclude '/inbox' \
      --exclude '/inbox/**' \
      --exclude '.env' \
      --exclude '.requirements.md5' \
      ./ "$PI_USER@$PI_HOST:$DIR/"

    # 3. Dienst auf dem Pi einrichten und neu starten
    echo "⚙️  [3/4 → $t] Konfiguriere und starte '$SERVICE' (Port $PORT)..."
    ssh "$PI_USER@$PI_HOST" bash -s "$DIR" "$SERVICE" "$PORT" "$INSTALL_DEPS" << 'EOF'
set -e
DIR="$1"
SERVICE="$2"
PORT="$3"
INSTALL_DEPS="$4"
cd "$DIR"

if [ ! -f ".env" ]; then
    echo "❌ $DIR/.env fehlt (KI-Schlüssel; bei Staging auch DATA_DIR/INBOX_DIR). Abbruch, Dienst nicht angefasst."
    exit 1
fi

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
    echo "📦 Aktualisiere Abhängigkeiten..."
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet -r backend/requirements.txt
    echo "$CURRENT_REQ_HASH" > .requirements.md5
else
    echo "⚡ Python-Abhängigkeiten unverändert (Überspringe pip install)."
fi

# 3. Nur den eigenen Systemd-Dienst aktualisieren und neu starten
sudo cp "$SERVICE.service" "/etc/systemd/system/$SERVICE.service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE.service"
sudo systemctl restart "$SERVICE.service"

# 4. Warten, bis der Dienst antwortet
for i in $(seq 1 30); do
    if curl -sf "http://localhost:$PORT/api/health" > /dev/null; then
        echo "🔄 '$SERVICE' läuft wieder (Port $PORT)."
        exit 0
    fi
    sleep 1
done
echo "❌ '$SERVICE' antwortet nach 30 s nicht. Logs: sudo journalctl -u $SERVICE -n 50"
exit 1
EOF
done

echo "✅ [4/4] Deployment abgeschlossen ($TARGET_ENV)!"
echo "👉 🟢 PRODUKTION (geschützte Daten): http://$PI_HOST:8000"
echo "👉 🟡 STAGING    (Test-Spielwiese):  http://$PI_HOST:8001"
