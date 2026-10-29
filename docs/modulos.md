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

Biblioteca unificada: **juegos de Steam** (los de tu cuenta, instalados o no), **juegos de emulador** detectados en `/run/media/deck/*`, `~/Emulation/roms` y `~/RetroHub/roms`, y otros accesos directos.

- Vista de **portadas** (cuadrícula con la portada actual de Steam) o de **lista**.
- Filtros por origen (Steam, Emulación, Otros), solo instalados, consola y búsqueda; orden por jugados recientemente, nombre, tiempo jugado o tamaño.
- Insignia de compatibilidad con Steam Deck (Verificado, Jugable, No compatible).
- **Switch**: agrupa juego base, actualizaciones y DLC por Title ID; marca la última actualización, las antiguas sobrantes y los DLC huérfanos.
- **Agregar a Steam** los juegos de emulador: crea el acceso directo con el emulador correcto, en una colección por consola.

### Detalle de un juego

Al hacer clic en un juego se abre su ficha, con el fondo y el logo actuales:

- **Resumen**: tiempo jugado, últimas 2 semanas, última vez, tamaño, carpeta, build, si hay una actualización pendiente, valoración de ProtonDB y AppID. En los de emulador: archivo, Title ID, versión, actualizaciones/DLC y emulador.
- **Carátulas**: las 4 imágenes actuales y las opciones de SteamGridDB de cada tipo.
- **Ejecución**: ▶ Jugar (abre el juego en el Deck), opciones de lanzamiento (con atajos como MangoHud o el registro de Proton) y versión de Proton. En los de emulador, las opciones del acceso directo.
- **Opciones**: ocultar en la biblioteca de Steam, agregar/quitar de Steam, ir a partidas guardadas, trucos o a la carpeta.

Los cambios los aplica el plugin dentro de Steam en unos segundos.

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

## Ofertas

Seguimiento de precios de la tienda de Steam, en la moneda de tu región (se detecta sola; se puede cambiar).

- **Importar mi lista de deseados** (el perfil debe tener los detalles de juegos públicos) o **buscar** cualquier juego y seguirlo.
- Por juego: precio actual, descuento y hasta cuándo, compatibilidad con Steam Deck, reseñas y **mínimo histórico**. Sin clave, es el más bajo que DeckHub ha visto; con una clave gratuita de [IsThereAnyDeal](https://isthereanydeal.com/apps/my/), el mínimo histórico real en Steam para tu región.
- **Alertas**: precio objetivo y/o «avisar en mínimo histórico». El daemon revisa cada 6 horas y el plugin muestra una notificación en el Deck; al tocarla abre el juego en la tienda.
- Solo lectura: DeckHub nunca compra ni toca tu cuenta.

## Personalización

- **Portadas de la biblioteca**: tus juegos instalados aparecen con su portada actual. Al elegir uno (o buscar cualquier juego de la biblioteca) se ven sus 4 imágenes actuales (portada vertical, horizontal, fondo y logo; marcadas como originales o personalizadas) y las opciones de SteamGridDB de cada tipo. Un clic aplica la imagen en Steam. «Restaurar originales» quita las personalizadas.
- **Temas del modo juego**: explora DeckThemes por categoría, instala, activa/desactiva y quita temas. Con [CSS Loader](https://deckthemes.com) instalado, la instalación la hace CSS Loader (incluidas las dependencias, como los temas de un perfil) y su lista se recarga sola. Si falta, el botón «Instalar CSS Loader» lo pide a Decky, que muestra su confirmación en la pantalla del Deck.
- **Videos de arranque**: sube `.webm` a `~/.local/share/Steam/config/uioverrides/movies/`; se eligen en Steam → Ajustes → Personalización. «Usar siempre» lo copia como `deck_startup.webm`, que tiene prioridad. **Recomendados**: videos de la comunidad de [steamdeckrepo.com](https://steamdeckrepo.com) (tendencia, más descargados, búsqueda) con vista previa y descarga en un clic.
- **Fondo de escritorio** (KDE): sube imágenes o elige las del sistema. En modo juego se guarda y se aplica al entrar al escritorio. **Recomendados**: fondos de [Wallhaven](https://wallhaven.cc) filtrados como aptos para todos (SFW), con búsqueda y categorías; «Usar de fondo» lo descarga y aplica.

Todo lo que se quita va a la papelera.

## Tiempo de juego

Horas totales, últimas 2 semanas y última vez jugado de toda tu biblioteca de Steam, con filtros (Steam, accesos directos, instalados) y búsqueda. El plugin de Decky envía los datos cada 5 minutos.

Los accesos directos de emuladores aparecen sin horas: Steam no registra el tiempo de los juegos que no son de Steam.

## Trucos

- **PS2**: identifica cada ISO (serial + CRC), edita su `.pnach` y activa o desactiva los trucos (PCSX2 debe estar cerrado).
- **Switch (Eden)**: pega trucos por juego con nombre y Build ID; activar/desactivar los mueve entre la carpeta de Eden y una de reserva.

## Ajustes

- **Acceso al panel**: permitir o no el acceso desde la red (puerto 8765). Si se cierra, el panel solo responde en el propio Deck; se vuelve a abrir desde el plugin.
- **Portadas**: clave de SteamGridDB y búsqueda automática.

## Tareas

Progreso de operaciones largas: copias, instalaciones, firmware, copias de seguridad.

## Plugin de Decky (menú rápido)

- Resumen del sistema.
- **Panel web**: abrir/cerrar el acceso desde la red, dirección y token.
- Interruptor para montar/desmontar unidades.
- Aplica accesos directos, colecciones y portadas en Steam, y avisa con una notificación.
- Botón para abrir el panel web.
