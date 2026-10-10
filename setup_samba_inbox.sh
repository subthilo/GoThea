#!/bin/bash
set -e

PI_USER="${PI_USER:-pi}"
PI_HOST="${PI_HOST:-192.168.1.135}"
INBOX_DIR="/home/$PI_USER/GoThea/inbox"
SHARE_NAME="GoThea-Inbox"

echo "================================================================="
echo "🍓 GoThea – Samba (SMB) Setup für Mac Finder Dropzone"
echo "================================================================="
echo "Target Pi: $PI_USER@$PI_HOST"
echo "Inbox Pfad: $INBOX_DIR"
echo "Freigabename: $SHARE_NAME"
echo ""

# 1. Verbindung prüfen
echo "📡 [1/4] Prüfe SSH-Verbindung zum Pi..."
ssh -o ConnectTimeout=5 "$PI_USER@$PI_HOST" "hostname" > /dev/null
echo "✅ SSH-Verbindung erfolgreich!"

# 2. Inbox-Verzeichnisse anlegen (staging & prod)
echo "📁 [2/4] Erstelle getrennte Inbox-Verzeichnisse für Staging & Prod..."
ssh "$PI_USER@$PI_HOST" "mkdir -p '$INBOX_DIR/staging' '$INBOX_DIR/prod' && chmod -R 777 '$INBOX_DIR'"
echo "✅ Verzeichnisse $INBOX_DIR/staging und $INBOX_DIR/prod bereit (Rechte: 777)."

# 3. Samba installieren & konfigurieren
echo "📦 [3/4] Konfiguriere Samba-Freigaben auf dem Pi..."
ssh "$PI_USER@$PI_HOST" bash -s "$SHARE_NAME" "$INBOX_DIR" << 'EOF'
set -e
SHARE="$1"
PATH_DIR="$2"

# A. Samba installieren falls nicht vorhanden
if ! which smbd > /dev/null 2>&1; then
    echo "  -> Aktualisiere Paketlisten und installiere Samba..."
    sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq samba samba-common-bin
fi

# B. Backup von smb.conf anlegen
if [ ! -f /etc/samba/smb.conf.gothea_bak ]; then
    sudo cp /etc/samba/smb.conf /etc/samba/smb.conf.gothea_bak
fi

# C. Prüfen, ob globale macOS / vfs_fruit Einstellungen vorhanden sind
if ! grep -q "fruit:metadata" /etc/samba/smb.conf; then
    echo "  -> Aktiviere macOS Apple-Extensions (vfs_fruit) in [global]..."
    sudo sed -i '/\[global\]/a \   min protocol = SMB2\n   ea support = yes\n   vfs objects = catia fruit streams_xattr\n   fruit:metadata = stream\n   fruit:model = MacMini\n   fruit:posix_rename = yes\n   map to guest = bad user' /etc/samba/smb.conf
fi

# D. Freigaben einrichten: GoThea-Inbox (Gesamt), GoThea-Staging, GoThea-Prod
sudo sed -i '/\[GoThea-Inbox\]/,$d' /etc/samba/smb.conf
sudo sed -i '/\[GoThea-Staging\]/,$d' /etc/samba/smb.conf
sudo sed -i '/\[GoThea-Prod\]/,$d' /etc/samba/smb.conf

cat << SMB_SECTION | sudo tee -a /etc/samba/smb.conf > /dev/null

[GoThea-Inbox]
   comment = GoThea Hauptordner (enthält staging und prod)
   path = $PATH_DIR
   browseable = yes
   read only = no
   guest ok = yes
   writeable = yes
   create mask = 0777
   directory mask = 0777
   force user = pi
   force group = pi
   public = yes

[GoThea-Staging]
   comment = GoThea STAGING Dropzone (Testdaten Port 8001)
   path = $PATH_DIR/staging
   browseable = yes
   read only = no
   guest ok = yes
   writeable = yes
   create mask = 0777
   directory mask = 0777
   force user = pi
   force group = pi
   public = yes

[GoThea-Prod]
   comment = GoThea PRODUKTION Dropzone (Echtdaten Port 8000)
   path = $PATH_DIR/prod
   browseable = yes
   read only = no
   guest ok = yes
   writeable = yes
   create mask = 0777
   directory mask = 0777
   force user = pi
   force group = pi
   public = yes
SMB_SECTION

# E. Dienste neu starten & aktivieren
echo "  -> Starte Samba-Dienste neu..."
sudo systemctl enable smbd nmbd > /dev/null 2>&1 || true
sudo systemctl restart smbd nmbd
EOF

echo "✅ Samba erfolgreich auf dem Pi aktualisiert und neu gestartet!"

# 4. Anleitung für macOS Finder
echo ""
echo "================================================================="
echo "🎉 ERFOLG! Der Netzwerkordner ist jetzt aktiv!"
echo "================================================================="
echo ""
echo "👉 So verbindest du dich im Mac Finder:"
echo "   1. Drücke im Finder: ⌘K (Gehe zu -> Mit Server verbinden...)"
echo "   2. Gib folgende Serveradresse ein:"
echo "      smb://$PI_HOST/$SHARE_NAME"
echo "      (oder: smb://Mothership.local/$SHARE_NAME)"
echo "   3. Klicke auf 'Verbinden'."
echo "   4. Wähle 'Als Gast verbinden' (oder Name: pi)."
echo ""
echo "📁 Ab jetzt kannst du PDFs, Scans und Bücher einfach in diesen"
echo "   gemounteten Ordner schaufeln!"
echo "================================================================="
