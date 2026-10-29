# DeckHub

Supervisor y centro retro para el **Steam Deck**: un servicio en el propio Deck, un panel web para manejarlo desde el PC o el móvil, y un plugin de [Decky Loader](https://decky.xyz) para verlo desde el menú de acceso rápido.

DeckHub cubre lo que Decky no toca: unidades y microSD, archivos, paquetes Flatpak, emuladores, accesos directos de Steam con portadas, partidas guardadas y trucos.

> **Estado:** versión 0.3 (en desarrollo). Probado en SteamOS 3.9 (Steam Deck LCD) con Decky Loader 3.3. Se instala como un plugin de Decky desde un zip; aún no está en la tienda de Decky ([hoja de ruta](docs/roadmap.md)).

*English summary below.*

## Funciones

| Módulo | Qué hace |
|---|---|
| **Resumen** | CPU, GPU, temperatura, batería, RAM, red, servicios y estado de Steam en tiempo real. |
| **Unidades y espacio** | Monta/desmonta la microSD y discos USB, automontaje al arrancar, análisis de qué ocupa espacio. |
| **Archivos** | Explorador web: subir, descargar, copiar, mover, renombrar. Borrar siempre manda a la papelera. |
| **Paquetes** | Buscar, instalar y desinstalar aplicaciones Flatpak. |
| **Juegos** | Detecta ROMs de PS2 y Switch (y otras consolas), agrupa actualizaciones y DLC de Switch, crea accesos directos en Steam con un clic. |
| **Portadas** | Descarga automáticamente grid, hero, logo y banner desde SteamGridDB (con tu propia clave API). |
| **Emuladores** | Instala y configura PCSX2, Eden, RetroArch, Dolphin, PPSSPP y más; instala firmware y llaves de Switch **que tú aportas**. |
| **Partidas** | Copias de seguridad diarias y manuales en zip, restauración y migración de yuzu → Eden. |
| **Trucos** | Gestiona `.pnach` de PCSX2 y trucos de Eden: pegar, activar, desactivar. |
| **Plugin de Decky** | Estado del sistema en el menú rápido, montar la microSD con un toque y aplicar los accesos directos y portadas en Steam. |

## Cómo está hecho

```
PC / móvil ──HTTP──▶ daemon (Python, aiohttp, :8765) ◀──── plugin de Decky (React + Python)
                         │                                   │
                         ├─ sistema, discos, Flatpak         └─ SteamClient: accesos directos,
                         ├─ emuladores y ROMs                   colecciones y portadas
                         └─ SteamGridDB, copias de seguridad
```

El repositorio es un plugin de Decky: al cargarse, el plugin instala y arranca el daemon como servicio `systemd --user`.

- [`src/`](src): interfaz del menú rápido (TypeScript/React).
- [`main.py`](main.py): backend del plugin; instala el daemon y hace de puente.
- [`py_modules/deckhub/`](py_modules/deckhub): el daemon (Python + `aiohttp`, ambos incluidos en SteamOS) y el panel web.
- [`scripts/`](scripts): despliegue de desarrollo y empaquetado del zip.
- [`docs/`](docs): documentación.

Detalles en [docs/arquitectura.md](docs/arquitectura.md).

## Instalación

1. Descarga `DeckHub-x.y.z.zip` de [Releases](../../releases).
2. En el Deck: Decky → Ajustes → General → activa **Modo desarrollador**; luego Decky → Ajustes → Desarrollador → **Instalar plugin desde ZIP**.
3. Abre DeckHub en el menú rápido: la sección **Panel web** muestra la dirección y el token para entrar desde el PC o el móvil.

Guía completa (y despliegue para desarrollo) en [docs/instalacion.md](docs/instalacion.md).

## Documentación

- [Instalación](docs/instalacion.md)
- [Arquitectura](docs/arquitectura.md)
- [Módulos y uso](docs/modulos.md)
- [API HTTP](docs/api.md)
- [Hoja de ruta](docs/roadmap.md)
- [Cambios](CHANGELOG.md)

## Aviso legal

DeckHub **no incluye ni descarga** juegos, BIOS, firmware ni llaves. Solo coloca en su sitio los archivos que tú obtienes de tus propias consolas y copias de juegos. Usa emuladores y contenido de forma legal en tu país.

DeckHub no está afiliado a Valve, Nintendo, Sony ni a los proyectos de los emuladores.

## Licencia

[MIT](LICENSE)

---

## English summary

**DeckHub** is a system supervisor and retro-gaming hub for the Steam Deck. It runs a small Python service on the Deck with a web dashboard (use it from your PC or phone) plus a Decky Loader plugin for the Quick Access menu.

It handles what Decky doesn't: microSD/USB mounting and automount, a web file manager, Flatpak packages, emulator install/config (PCSX2, Eden, RetroArch…), one-click Steam shortcuts with automatic SteamGridDB artwork, Switch update/DLC grouping, save backups and cheats.

Install it as a Decky plugin from the zip in Releases (Decky → Developer → Install plugin from ZIP); the plugin sets up the background service by itself. It does **not** ship or download games, BIOS, firmware or keys; you supply your own dumps. The UI is currently in Spanish. Not yet on the Decky store; see the [roadmap](docs/roadmap.md).
