# Arquitectura

DeckHub tiene tres piezas que se comunican por HTTP local.

```
┌──────────── Steam Deck ───────────────────────────────────────────┐
│                                                                   │
│  daemon  (systemd --user, python3 -m deckhub, puerto 8765)        │
│   ├─ API JSON  /api/...                                           │
│   ├─ panel web /  (web/index.html, sin compilación)               │
│   └─ tareas de fondo: automontaje, portadas, copias diarias       │
│          ▲                                                        │
│          │ HTTP 127.0.0.1 + token                                 │
│  plugin de Decky                                                  │
│   ├─ main.py   backend Python: lee el token, hace de puente       │
│   └─ src/      frontend React: menú rápido + SteamClient          │
└──────────▲────────────────────────────────────────────────────────┘
           │ HTTP en la red local
      PC / móvil (navegador)
```

## Daemon (`py_modules/deckhub/`)

| Archivo | Papel |
|---|---|
| `__main__.py` | Arranca aiohttp, registra rutas y lanza las tareas de fondo. |
| `auth.py` | Token en cabecera `X-DeckHub-Token` o cookie `deckhub_token`. Las lecturas de estado son públicas en la red local; todo lo demás exige token. |
| `config.py` | `~/.config/deckhub/config.json` y el token (`~/.config/deckhub/token`, se genera en el primer arranque). |
| `routes.py` | Rutas protegidas; convierte errores en JSON legible. |
| `fileops.py` | Operaciones de archivo limitadas a `/home/deck` y `/run/media/deck`. Borrar = papelera freedesktop. |
| `jobs.py` | Tareas largas en hilos con progreso (`done/total`), visibles en la pestaña Tareas. |
| `ini.py` | Editor de `.ini` por líneas que respeta el formato y hace una copia `.deckhub.bak`. |
| `modules/` | Un archivo por área (ver abajo). |
| `web/index.html` | Panel completo en un solo archivo HTML/JS. |

### Módulos

| Módulo | Contenido |
|---|---|
| `system`, `network`, `steam`, `services` | Estado de solo lectura (hwmon, `/proc`, NetworkManager, procesos). |
| `storage` | Discos extraíbles con `udisksctl`, automontaje. |
| `packages` | Flatpak: listar, buscar, instalar, desinstalar. |
| `roms` | Escanea carpetas de juegos, clasifica por consola, agrupa base/actualización/DLC de Switch por Title ID. |
| `ps2ids` | Lee serial y CRC del ELF dentro de la ISO (como PCSX2), con caché. |
| `emulators` | Catálogo, instalación y configuración automática; firmware y llaves de Eden. |
| `shortcuts` | Cola de accesos directos y portadas que aplica el plugin. |
| `artwork` | Cliente de SteamGridDB; caché en `~/.cache/deckhub/art/<appid>`. |
| `saves` | Copias zip en `~/DeckHub/backups/<emulador>/`, restaurar, migrar yuzu → Eden. |
| `cheats` | `.pnach` de PCSX2 y trucos de Eden. |

Cada módulo de estado expone `async def collect() -> dict` y se registra en `modules/__init__.py`.

## Plugin (raíz del repositorio)

- `main.py`: backend de Decky (corre como `deck`).
  - Al cargar (`_main`) escribe `~/.config/systemd/user/deckhub.service` apuntando a `<carpeta del plugin>/py_modules` y arranca el daemon; si la versión en marcha no coincide con la incluida, lo reinicia.
  - Al desinstalar (`_uninstall`) desactiva y borra el servicio; los datos se conservan.
  - Al descargarse (`_unload`) deja el daemon en marcha, para que el panel web siga funcionando si Decky se reinicia.
  - Hace de puente: lee el token y llama al daemon en `127.0.0.1:8765`.
- `src/index.tsx`: panel del menú rápido (sistema, unidades, red, Steam, dirección y token del panel web).
- `src/shortcuts.ts`: cada 5 s pide al daemon la cola pendiente y la aplica con la API interna de Steam (`SteamClient.Apps.AddShortcut`, `SetCustomArtworkForApp`, colecciones). Así el daemon nunca edita `shortcuts.vdf` con Steam abierto.
  - En el mismo ciclo aplica las portadas personalizadas y las acciones de Decky: instalar un plugin de la tienda (`utilities/install_plugin`, con la confirmación de Decky) y recargar CSS Loader (`reset`).

## Principios

- **Nada se borra definitivamente**: archivos, firmware, llaves y trucos van a la papelera.
- **Sin root**: todo corre como `deck`. Lo único con `sudo` es para desarrollo (preparar la carpeta y reiniciar Decky).
- **Sin contenido con derechos de autor**: DeckHub no descarga juegos, BIOS, firmware ni llaves.
- **Un módulo roto no tumba el resto**: los errores se devuelven por módulo.

## Datos en el Deck

| Ruta | Contenido |
|---|---|
| `~/homebrew/plugins/DeckHub/` | Plugin y daemon (`py_modules/deckhub`). |
| `~/.config/systemd/user/deckhub.service` | Servicio, escrito por el plugin. |
| `~/.config/deckhub/` | `config.json`, `token`, `shortcuts.json`. |
| `~/.cache/deckhub/` | Portadas, caché de IDs de PS2, subidas temporales. |
| `~/DeckHub/backups/` | Copias de partidas. |
| `~/.local/share/deckhub/cheats-off/` | Trucos de Eden desactivados. |
