# Módulos y uso

Guía de cada pestaña del panel web (`http://<ip-del-deck>:8765`). Las acciones que cambian algo piden el token una vez por navegador.

## Resumen

Estado en vivo: CPU, GPU, temperaturas, batería, RAM, red, servicios y si Steam está en modo juego o escritorio. Es lo único visible sin token.

## Unidades y espacio

- Montar y desmontar la microSD y discos USB (solo dispositivos extraíbles).
- **Automontaje**: marca una unidad y DeckHub la monta al arrancar y cada 30 s si se inserta después.
- **Espacio**: qué carpetas ocupan más, para limpiar.

## Archivos

Explorador de `/home/deck` y `/run/media/deck`: subir (arrastrar y soltar), descargar, crear carpetas, renombrar, copiar y mover (como tarea con progreso). **Borrar manda a la papelera**.

## Paquetes

Busca, instala y desinstala aplicaciones Flatpak de Flathub (de usuario).

## Juegos

Escanea `/run/media/deck/*`, `~/Emulation/roms` y `~/RetroHub/roms`.

- Clasifica por consola según extensión y carpeta (PS2, Switch, PSP, GameCube/Wii, 3DS, etc.).
- **Switch**: agrupa juego base, actualizaciones y DLC por Title ID; marca la última actualización, las antiguas sobrantes y los DLC huérfanos.
- **Añadir a Steam**: crea el acceso directo con el emulador correcto, en una colección por consola. Lo aplica el plugin de Decky en segundos.
- Muestra si cada juego ya está en Steam y el estado de sus portadas.

## Portadas (Ajustes)

1. Crea una clave API gratuita en [steamgriddb.com/profile/preferences/api](https://www.steamgriddb.com/profile/preferences/api).
2. Pégala en **Ajustes**. DeckHub la valida antes de guardarla.
3. Con «Portadas automáticas», cada acceso directo nuevo recibe grid, hero, logo y banner. «Actualizar todas» vuelve a pedirlas.

## Emuladores

- Lista el catálogo (PCSX2, Eden, Ryubing, RetroArch, PPSSPP, Dolphin, Azahar, melonDS, Cemu, Flycast, xemu) con su estado: instalado, configurado, avisos.
- **Instalar**: Flatpak desde Flathub.
- **Configurar**: rutas de juegos, BIOS, pantalla completa y permisos de lectura de la microSD.

### Firmware y llaves de Switch (Eden)

DeckHub **no** proporciona firmware ni llaves: deben salir de tu propia consola.

- **Instalar firmware (.zip)**: sube el zip desde el PC; se extraen los `.nca` en la NAND de Eden.
- **Desde una ruta del Deck**: un zip o carpeta que ya esté en el Deck o la microSD.
- **Actualizar llaves**: `prod.keys` (y opcional `title.keys`). Deben ser de la misma versión que el firmware o más nuevas.

Comprobaciones: el zip debe tener al menos 20 `.nca`, las llaves deben contener `header_key` y Eden debe estar cerrado. El firmware y las llaves anteriores van a la papelera.

## Partidas

- Copias zip por emulador en `~/DeckHub/backups/<emulador>/`.
- **Copia diaria automática** (configurable) que conserva las últimas N; las manuales no se borran nunca.
- **Restaurar**: antes de restaurar se hace una copia de lo actual.
- **Migrar de yuzu a Eden**: copia partidas y perfil.

## Trucos

- **PS2**: identifica cada ISO (serial + CRC), edita su `.pnach` y activa o desactiva los trucos (PCSX2 debe estar cerrado).
- **Switch (Eden)**: pega trucos por juego con nombre y Build ID; activar/desactivar los mueve entre la carpeta de Eden y una de reserva.

## Tareas

Progreso de operaciones largas: copias, instalaciones, firmware, copias de seguridad.

## Plugin de Decky (menú rápido)

- Resumen del sistema.
- Interruptor para montar/desmontar unidades.
- Aplica accesos directos, colecciones y portadas en Steam, y avisa con una notificación.
- Botón para abrir el panel web.
