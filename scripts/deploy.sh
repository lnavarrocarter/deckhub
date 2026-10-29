#!/bin/sh
# Compila el plugin y lo copia a Decky en el Deck (desarrollo). Uso: scripts/deploy.sh [host-ssh]
# Al cargarse, el plugin instala/actualiza el daemon como servicio de usuario.
set -e
HOST="${1:-steamdeck}"
cd "$(dirname "$0")/.."

pnpm build
# Decky deja la carpeta del plugin y plugin.json como root: los demás archivos se
# sobrescriben en su sitio. La primera vez hay que preparar la carpeta con sudo
# (ver docs/instalacion.md).
tar --exclude=__pycache__ -cf - main.py package.json dist/index.js py_modules | ssh "$HOST" '
  set -e
  D=~/homebrew/plugins/DeckHub
  if [ ! -w "$D/py_modules" ]; then
    echo "Falta preparar $D/py_modules (una sola vez):" >&2
    echo "  ssh -t '"$HOST"' \"sudo mkdir -p $D/py_modules && sudo chown -R deck:deck $D/py_modules\"" >&2
    exit 1
  fi
  tar -C "$D" --overwrite -xf -
  # La recarga en caliente de Decky no es fiable: se reinicia con la regla de
  # /etc/sudoers.d/zz-deckhub-decky (solo permite este comando, sin contraseña).
  if sudo -n systemctl restart plugin_loader 2>/dev/null; then
    echo "desplegado en $D (Decky reiniciado)"
  else
    echo "desplegado en $D (reinicia Decky para cargarlo)"
  fi
'
