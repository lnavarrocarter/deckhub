# Hoja de ruta

Objetivo: que DeckHub se instale desde la **tienda de Decky** con un clic, y publicarlo en Reddit (r/SteamDeck, r/SteamDeckHomebrew, r/EmulationOnSteamDeck).

## Hacia la tienda de Decky

La tienda ([decky-plugin-database](https://github.com/SteamDeckHomebrew/decky-plugin-database)) instala un solo plugin. Desde la 0.3 el daemon viaja dentro del plugin y se instala solo.

- [x] **Empaquetar el daemon dentro del plugin**: incluir `daemon/deckhub` en el zip del plugin y que `main.py` lo arranque (como proceso hijo, o instalando el servicio `systemd --user` en `_main`) y lo detenga en `_unload` / `_uninstall`.
- [x] Ajustar rutas: el código pasa de `~/deckhub` a la carpeta del plugin (`DECKY_PLUGIN_DIR`); los datos siguen en `~/.config/deckhub`.
- [x] Quitar el flag `debug` de `plugin.json`.
- [ ] Añadir imagen de portada para la tienda.
- [x] Mostrar la dirección y el token del panel en el plugin (sin SSH).
- [ ] Código QR del panel en el plugin.
- [x] Regla sudo solo para desarrollo (instalado desde zip no hace falta).
- [x] GitHub Actions genera el zip en cada etiqueta `v*`.
- [ ] Comprobar el build con la CLI oficial de Decky (la que usa la tienda).
- [ ] Avisar en la interfaz si la red no llega a SteamGridDB por IPv4 y ofrecer activar IPv6.
- [ ] Probar en Steam Deck OLED y en una instalación limpia.
- [ ] Enviar el PR a `decky-plugin-database`.

## Antes de publicar en Reddit

- [ ] Hacer público el repositorio.
- [ ] Capturas y GIF del panel y del menú rápido en el README.
- [ ] Interfaz en inglés (i18n español/inglés).
- [ ] Guía de instalación manual con el zip de Releases para quien no quiera esperar a la tienda.

## Mejoras pendientes

- [ ] Acelerar la pestaña Emuladores (hoy tarda ~10 s revisando permisos Flatpak uno a uno).
- [ ] Verificar que Eden carga actualizaciones/DLC desde las carpetas de juegos.
- [ ] Probar trucos reales de PCSX2 y Eden.
- [ ] Más consolas en la detección de Title ID / seriales.
- [ ] Opción de escuchar solo en localhost o exigir token también para el resumen.
