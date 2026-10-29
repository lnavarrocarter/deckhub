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

## Control total del Deck desde el hub

Objetivo: que DeckHub abarque la mayor parte de la configuración del Deck, desde el panel web y desde el plugin.

### Hecho

- [x] Abrir/cerrar el panel a la red (puerto 8765) desde el plugin y desde Ajustes.
- [x] Tiempo de juego de toda la biblioteca (total, últimas 2 semanas, última vez).

### Fase A · Personalización

- [ ] **Videos de arranque**: subir `.webm` a `~/.steam/root/config/uioverrides/movies/` y elegirlos (Steam los lista en Ajustes → Personalización).
- [ ] **Portadas de toda la biblioteca**: elegir entre varias opciones de SteamGridDB para cualquier juego (no solo accesos directos) con vista previa; restaurar la original.
- [ ] **Temas (skins) del modo juego**: integración con CSS Loader / DeckThemes: explorar, instalar, activar y desactivar temas desde el panel.
- [ ] **Fondos de pantalla**: escritorio KDE (`plasma-apply-wallpaperimage`) y fondo del modo juego mediante tema.

### Fase B · Sistema y rendimiento en el plugin

- [ ] Perfiles de rendimiento (TDP, GPU, FPS) por juego desde el plugin, si la API de Steam lo permite sin root.
- [ ] Gestión de unidades ampliada en el plugin: expulsar, espacio libre, automontaje.
- [ ] Formatear microSD/USB (exFAT/ext4) con doble confirmación.
- [ ] **Particionar discos**: alto riesgo de pérdida de datos; solo discos externos, nunca el interno, con vista previa y confirmación escrita.

### Fase C · Biblioteca

- [ ] Ocultar/mostrar juegos y gestionar colecciones desde el panel.
- [ ] Tiempo de juego de los accesos directos de emuladores (Steam no lo registra; medirlo con el daemon mientras el emulador está abierto).

## Mejoras pendientes

- [ ] Acelerar la pestaña Emuladores (hoy tarda ~10 s revisando permisos Flatpak uno a uno).
- [ ] Verificar que Eden carga actualizaciones/DLC desde las carpetas de juegos.
- [ ] Probar trucos reales de PCSX2 y Eden.
- [ ] Más consolas en la detección de Title ID / seriales.
- [ ] Opción de escuchar solo en localhost o exigir token también para el resumen.
