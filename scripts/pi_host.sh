#!/bin/bash
# Wählt den Weg zum Pi: zuhause direkt übers WLAN, unterwegs über Tailscale.
#   source scripts/pi_host.sh   -> setzt PI_HOST (ein schon gesetztes PI_HOST gewinnt)
#   scripts/pi_host.sh          -> gibt die Adresse aus, z. B. ssh pi@$(scripts/pi_host.sh)
#
# Zuhause gilt nur, wenn sich der Pi per SSH mit seinem bekannten Schlüssel meldet:
# In fremden Netzen kann unter 192.168.1.135 ein anderes Gerät antworten.

PI_LAN_HOST="192.168.1.135"
PI_TAILSCALE_HOST="gothea-pi"

pick_pi_host() {
    if ssh -o BatchMode=yes -o ConnectTimeout=2 -o StrictHostKeyChecking=yes \
           "${PI_USER:-pi}@$PI_LAN_HOST" true 2>/dev/null; then
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
