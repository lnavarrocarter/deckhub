# Instalación

DeckHub es un plugin de [Decky Loader](https://decky.xyz). Al cargarse, el plugin instala el daemon (servicio `systemd --user`) que sirve el panel web; no hace falta SSH ni root.

## Requisitos

- Steam Deck con SteamOS 3.6 o superior (probado en 3.9).
- Decky Loader 3.x.

El daemon usa el Python 3 y el `aiohttp` que ya trae SteamOS.

## Instalar desde el zip (usuarios)

1. Descarga `DeckHub-x.y.z.zip` de la página de **Releases** del repositorio.
2. En el Deck: menú rápido → Decky → ⚙ Ajustes → General → activa **Modo desarrollador**.
3. Decky → Ajustes → **Desarrollador** → «Instalar plugin desde ZIP» (o «desde URL» pegando el enlace del zip de Releases).
4. Abre DeckHub en el menú rápido. La sección **Panel web** muestra la dirección (`http://<ip-del-deck>:8765`) y el botón **Mostrar token**.
5. En el PC o el móvil, abre esa dirección y pega el token cuando el panel lo pida.

Para actualizar, instala el zip nuevo encima: el plugin detecta la versión y reinicia el daemon.

## Desinstalar

Quita el plugin desde Decky. El servicio se desactiva y se elimina; la configuración y los datos se conservan en `~/.config/deckhub`, `~/.cache/deckhub` y `~/DeckHub/backups` (copias de partidas). Bórralos a mano si no los quieres.

## Desarrollo

### En el PC

- `ssh`, `tar`, `sh` (Linux/macOS o Git Bash en Windows), Python 3.
- Node.js 20 y `pnpm`.

```bash
pnpm install
pnpm build                     # dist/index.js
python scripts/build-zip.py    # out/DeckHub-<versión>.zip
```

Al publicar una etiqueta `vX.Y.Z`, GitHub Actions compila y adjunta el zip a la Release (`.github/workflows/release.yml`).

### Acceso SSH al Deck

En modo escritorio, en **Konsole**:

```bash
passwd                    # si aún no tienes contraseña
sudo systemctl enable --now sshd
```

En el PC, un alias `steamdeck` en `~/.ssh/config` y tu clave copiada:

```
Host steamdeck
    HostName 192.168.1.50      # IP del Deck (Ajustes → Internet)
    User deck
```

```bash
ssh-copy-id steamdeck
```

### Desplegar al Deck

Instala el plugin una vez desde el zip (o crea la carpeta a mano) y prepara la carpeta del daemon, que Decky deja como root:

```bash
ssh -t steamdeck "sudo mkdir -p ~/homebrew/plugins/DeckHub/py_modules && sudo chown -R deck:deck ~/homebrew/plugins/DeckHub/py_modules"
```

Después, cada cambio:

```bash
scripts/deploy.sh steamdeck
```

Compila, copia `main.py`, `dist/` y `py_modules/` al plugin y reinicia Decky; el plugin reinicia el daemon si cambió la versión (`py_modules/deckhub/__init__.py`). Sube la versión en `package.json` y en `__init__.py` a la vez.

#### Opcional: reiniciar Decky sin contraseña

La recarga en caliente de Decky no siempre funciona. Esta regla permite a `deploy.sh` reiniciar solo `plugin_loader`. El nombre empieza por `zz-` para leerse después de la regla `wheel` de SteamOS (si no, esa la anula):

```bash
ssh -t steamdeck "echo 'deck ALL=(root) NOPASSWD: /usr/bin/systemctl restart plugin_loader' | sudo tee /etc/sudoers.d/zz-deckhub-decky && sudo chmod 440 /etc/sudoers.d/zz-deckhub-decky"
```

### Migrar desde la versión 0.2 (daemon en `~/deckhub`)

El plugin 0.3 reescribe `~/.config/systemd/user/deckhub.service` para usar su propia copia del daemon. La carpeta antigua `~/deckhub` ya no se usa y se puede mandar a la papelera.

## Problemas comunes

- **`sudo` pide contraseña en Windows**: los comandos con `sudo` se ejecutan en el Deck (Konsole o `ssh -t steamdeck '...'`), no en PowerShell.
- **El menú rápido dice «Daemon no disponible»**: pulsa «Reiniciar daemon». Si sigue, revisa `journalctl --user -u deckhub`.
- **Las portadas no se descargan**: Ajustes muestra el motivo. Si es «tiempo de espera agotado», la red no llega a `www.steamgriddb.com` por IPv4 (pasa con algunos proveedores). Activa IPv6 en la conexión wifi del Deck:

  ```bash
  sudo nmcli con modify "<nombre del wifi>" ipv6.method auto && sudo nmcli device reapply wlan0
  ```
