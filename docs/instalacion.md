# Instalación

Mientras DeckHub no esté en la tienda de Decky, se instala desde el código por SSH. Todo se hace desde un PC en la misma red que el Deck.

## Requisitos

| Dónde | Qué |
|---|---|
| Steam Deck | SteamOS 3.6 o superior (probado en 3.9), contraseña de `deck` configurada, [Decky Loader](https://decky.xyz) para el plugin. |
| PC | `ssh`, `tar`, `sh` (Linux/macOS, o Git Bash en Windows). Para el plugin: Node.js 18+ y `pnpm`. |

El daemon usa el Python 3 y el `aiohttp` que ya trae SteamOS: no hay que instalar nada en el Deck.

## 1. Activar SSH en el Deck

En modo escritorio, abre **Konsole**:

```bash
passwd                    # si aún no tienes contraseña
sudo systemctl enable --now sshd
```

En el PC, crea un alias `steamdeck` en `~/.ssh/config` y copia tu clave:

```
Host steamdeck
    HostName 192.168.1.50      # IP del Deck (Ajustes → Internet)
    User deck
```

```bash
ssh-copy-id steamdeck
```

## 2. Daemon y panel web

```bash
cd daemon
./deploy.sh steamdeck
```

Copia el código a `~/deckhub`, instala el servicio `~/.config/systemd/user/deckhub.service` y lo arranca. Debe responder `active`.

Abre `http://<ip-del-deck>:8765`. El resumen es público en tu red; para cualquier acción el panel pide el **token**, que está en el Deck:

```bash
ssh steamdeck cat ~/.config/deckhub/token
```

## 3. Plugin de Decky

```bash
cd plugin
pnpm install
```

La primera vez, crea la carpeta del plugin en el Deck (Decky la deja como root):

```bash
ssh -t steamdeck 'sudo mkdir -p ~/homebrew/plugins/DeckHub && sudo chown -R deck:deck ~/homebrew/plugins/DeckHub'
scp plugin.json steamdeck:homebrew/plugins/DeckHub/
```

Después, cada despliegue:

```bash
./deploy.sh steamdeck
```

### Opcional: reiniciar Decky sin contraseña

La recarga en caliente de Decky no siempre funciona. Esta regla permite a `deploy.sh` reiniciar solo `plugin_loader`. El nombre empieza por `zz-` para que se lea después de la regla `wheel` de SteamOS (si no, esa la anula):

```bash
ssh -t steamdeck "echo 'deck ALL=(root) NOPASSWD: /usr/bin/systemctl restart plugin_loader' | sudo tee /etc/sudoers.d/zz-deckhub-decky && sudo chmod 440 /etc/sudoers.d/zz-deckhub-decky"
```

## Desinstalar

```bash
ssh steamdeck 'systemctl --user disable --now deckhub; rm -rf ~/deckhub ~/.config/systemd/user/deckhub.service'
```

El plugin se quita desde Decky. Configuración y datos quedan en `~/.config/deckhub`, `~/.cache/deckhub` y `~/DeckHub/backups` (copias de partidas): bórralos a mano si no los quieres.

## Problemas comunes

- **`sudo` pide contraseña en Windows**: los comandos con `sudo` se ejecutan en el Deck (Konsole o `ssh -t steamdeck '...'`), no en PowerShell.
- **El plugin no aparece**: reinicia Decky (`sudo systemctl restart plugin_loader`) o el Deck.
- **Las portadas no se descargan**: revisa que el Deck llegue a `www.steamgriddb.com` (algunos routers o filtros DNS lo bloquean) y que la clave API sea válida.
