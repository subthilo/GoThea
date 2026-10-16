#!/bin/bash
# Wählt den Weg zum Pi: immer über Tailscale (gothea-pi), zuhause wie unterwegs.
# Ist Tailscale auf dem Mac aus, Rückfall auf die WLAN-Adresse.
#   source scripts/pi_host.sh   -> setzt PI_HOST (ein schon gesetztes PI_HOST gewinnt)
#   scripts/pi_host.sh          -> gibt die Adresse aus, z. B. ssh pi@$(scripts/pi_host.sh)
#
# Der Rückfall gilt nur, wenn sich der Pi per SSH mit seinem bekannten Schlüssel meldet:
# In fremden Netzen kann unter 192.168.1.135 ein anderes Gerät antworten.

PI_TAILSCALE_HOST="gothea-pi"
PI_LAN_HOST="192.168.1.135"

pi_answers() {
    ssh -o BatchMode=yes -o ConnectTimeout=3 -o StrictHostKeyChecking=yes \
        "${PI_USER:-pi}@$1" true 2>/dev/null
}

pick_pi_host() {
    if pi_answers "$PI_TAILSCALE_HOST"; then
        echo "$PI_TAILSCALE_HOST"
    elif pi_answers "$PI_LAN_HOST"; then
        echo "⚠️  Tailscale nicht erreichbar – nehme das WLAN ($PI_LAN_HOST)." >&2
        echo "$PI_LAN_HOST"
    else
        echo "$PI_TAILSCALE_HOST"
    fi
}

if [ -z "$PI_HOST" ]; then
    PI_HOST="$(pick_pi_host)"
fi

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    echo "$PI_HOST"
fi
