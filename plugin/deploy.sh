#!/bin/sh
# Compila el plugin y lo copia a Decky (recarga en caliente). Uso: ./deploy.sh [host-ssh]
set -e
HOST="${1:-steamdeck}"
cd "$(dirname "$0")"

pnpm build
# Decky deja la carpeta del plugin y plugin.json como root: se sobrescriben en su
# sitio solo los archivos que siguen siendo de deck. Cambiar plugin.json requiere sudo.
tar -cf - main.py package.json dist/index.js | ssh "$HOST" '
  set -e
  D=~/homebrew/plugins/DeckHub
  tar -C "$D" --overwrite -xf -
  # La recarga en caliente de Decky no es fiable: se reinicia con la regla de
  # /etc/sudoers.d/zz-deckhub-decky (solo permite este comando, sin contraseña).
  if sudo -n systemctl restart plugin_loader 2>/dev/null; then
    echo "desplegado en $D (Decky reiniciado)"
  else
    echo "desplegado en $D (reinicia Decky para cargarlo)"
  fi
'
