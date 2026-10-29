# Cambios

## 0.4.0 (2026-10-29)

- Interruptor para abrir/cerrar el panel a la red (puerto 8765), en el plugin y en Ajustes. Cerrado, el daemon escucha solo en 127.0.0.1 y el plugin sigue funcionando.
- Pestaña «Tiempo de juego»: horas de toda la biblioteca de Steam, enviadas por el plugin.

## 0.3.0 (2026-10-29)

- El repositorio pasa a ser un plugin de Decky: el daemon viaja en `py_modules/` y el plugin lo instala, actualiza y desinstala como servicio de usuario.
- Menú rápido: dirección y token del panel web, y botón «Reiniciar daemon».
- Zip instalable (`scripts/build-zip.py`) y GitHub Actions que lo publica en cada etiqueta.
- Portadas: mensajes de error claros, espera progresiva cuando no hay conexión y aviso en Ajustes.
- Se quita el modo `debug` del plugin.

## 0.2.0 (2026-10-28)

- Módulo retro: detección de ROMs (PS2, Switch y más) y agrupación de actualizaciones/DLC de Switch.
- Catálogo, instalación y configuración de emuladores (PCSX2, Eden, RetroArch…).
- Accesos directos en Steam con colecciones, aplicados desde el plugin.
- Portadas automáticas desde SteamGridDB.
- Copias de seguridad de partidas (diarias y manuales), restauración y migración yuzu → Eden.
- Trucos para PCSX2 y Eden.
- Instalación de firmware y llaves de Switch aportados por el usuario.
- Pestaña Ajustes.

## 0.1.0

- Daemon con panel web: sistema, unidades y microSD (montaje y automontaje), archivos, espacio y paquetes Flatpak.
- Plugin de Decky con resumen del sistema y montaje de unidades.
