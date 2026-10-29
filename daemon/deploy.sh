#!/bin/sh
# Copia el daemon al Deck y (re)inicia el servicio de usuario. Uso: ./deploy.sh [host-ssh]
set -e
HOST="${1:-steamdeck}"
cd "$(dirname "$0")"

tar --exclude=__pycache__ -cf - deckhub systemd | ssh "$HOST" '
  set -e
  mkdir -p ~/deckhub ~/.config/systemd/user
  rm -rf ~/deckhub/deckhub
  tar -C ~/deckhub -xf -
  cp ~/deckhub/systemd/deckhub.service ~/.config/systemd/user/
  systemctl --user daemon-reload
  systemctl --user enable deckhub >/dev/null 2>&1
  systemctl --user restart deckhub
  sleep 1
  systemctl --user is-active deckhub
'
