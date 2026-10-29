# Installation

DeckHub is a [Decky Loader](https://decky.xyz) plugin. When it loads, it installs its background service (a `systemd --user` unit) that serves the web dashboard. No SSH, no root, nothing to install on the Deck besides Decky.

## Requirements

- Steam Deck (LCD or OLED) with SteamOS 3.6 or newer (tested on 3.9).
- Decky Loader 3.x.

## 1. Install Decky Loader (if you don't have it)

1. Hold the power button → **Switch to Desktop**.
2. Open a browser, go to [decky.xyz](https://decky.xyz) and download the installer.
3. Run it, choose **Install latest release**, and go back to Game Mode.
4. A plug icon appears in the Quick Access menu (**⋯** button).

## 2. Install DeckHub

1. **⋯** → **Decky** → ⚙ **Settings** → **General** → turn on **Developer mode**.
2. **Developer** → **Install plugin from URL**, paste:

   ```
   https://github.com/lnavarrocarter/deckhub/releases/latest/download/DeckHub.zip
   ```

   Alternatively download the zip from the [Releases](../../releases) page and use **Install plugin from ZIP file**.
3. Confirm. DeckHub shows up in the Decky list.

## 3. Open the dashboard

In the Quick Access menu → DeckHub → **Web dashboard**:

- **Open the dashboard on the Deck** opens it in the Steam browser.
- **Network access** opens port 8765 on your local network; scan the **QR code** with your phone or type the address on your PC. Turn it off when you don't need it.
- **Show token**: the dashboard asks for this token the first time you change something. It is stored on the Deck only.

The language follows Steam (Settings → Language). You can override it with the 🌐 selector at the top of the dashboard.

## Update and uninstall

- **Update**: install the new zip the same way. The plugin restarts its service with the new version; settings are kept.
- **Uninstall**: Decky → Settings → Plugins → DeckHub → Uninstall. The service is removed. Settings, artwork cache and save backups stay in `~/.config/deckhub`, `~/.cache/deckhub` and `~/DeckHub/backups`; delete them by hand if you want.

## Troubleshooting

- **"The DeckHub service is not responding"** in the plugin: press **Restart service**. If it persists, run `journalctl --user -u deckhub` in Konsole (Desktop Mode).
- **The dashboard doesn't open from the PC**: check that **Network access** is on and that both devices are on the same network.
- **Artwork doesn't download**: Settings shows why. A timeout usually means your network can't reach SteamGridDB over IPv4; enabling IPv6 on the Deck's Wi-Fi fixes it:

  ```bash
  sudo nmcli con modify "<wifi name>" ipv6.method auto && sudo nmcli device reapply wlan0
  ```

## For developers

See [instalacion.md](instalacion.md#desarrollo) (Spanish) for building, `scripts/deploy.sh` and releases.
