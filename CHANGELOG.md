# Cambios

## 0.9.1 (2026-10-29)

- «Descargar todo» ya inicia las descargas: las llamadas a Steam llevan el equipo (este Deck), como hace la propia interfaz de Steam. Adelanta también las programadas por la restricción horaria de actualizaciones.
- La barra de «Descargar todo» se muestra abajo de la lista de Descargas.

## 0.9.0 (2026-10-29)

- «Descargar todo»: pone en cola e inicia todas las actualizaciones pendientes de Steam. Disponible en la página Descargas de Steam, en el menú rápido y en la pestaña Juegos del panel.

## 0.8.1 (2026-10-29)

- La lista de deseados se importa desde el cliente de Steam (con tu sesión) aunque el perfil no la muestre, y se sincroniza cada 30 minutos.
- Se guardan también ignorados, seguidos y etiquetas recomendadas de la tienda, para las recomendaciones.

## 0.8.0 (2026-10-29)

- Pestaña «Ofertas»: seguimiento de precios de Steam en tu moneda (lista de deseados o búsqueda), descuento y fin de la oferta, compatibilidad con Deck, reseñas y mínimo histórico (DeckHub o IsThereAnyDeal).
- Alertas por precio objetivo o mínimo histórico; revisión cada 6 horas y notificación en el Deck que abre la tienda.

## 0.7.0 (2026-10-29)

- Pestaña Juegos rehecha: biblioteca unificada (Steam + emulación + accesos directos) en cuadrícula de portadas o lista, con filtros, orden e insignia de compatibilidad con Steam Deck.
- Ficha de detalle por juego: resumen (tiempo, tamaño, ProtonDB, actualizaciones/DLC), carátulas, ejecución (Jugar, opciones de lanzamiento, Proton) y opciones (ocultar, agregar/quitar de Steam).
- El plugin aplica en Steam: jugar, opciones de lanzamiento, versión de Proton y ocultar.
- Editor de carátulas reutilizable (Personalización y detalle).

## 0.6.0 (2026-10-29)

- Temas: con CSS Loader instalado, instalar/activar pasa por CSS Loader (trae las dependencias de los perfiles) y su interfaz se recarga para mostrar los cambios. Antes los perfiles quedaban sin sus temas.
- Portadas: galería de juegos instalados con su portada actual; al elegir un juego se ven sus 4 imágenes actuales y las opciones de cada tipo a la vez.
- Videos de arranque recomendados de steamdeckrepo.com y fondos de escritorio de Wallhaven (solo SFW), con descarga en un clic.

## 0.5.2 (2026-10-29)

- Botón «Instalar CSS Loader» en Personalización: la instalación la hace Decky, con su confirmación en pantalla.
- Instalar, activar o quitar un tema recarga CSS Loader automáticamente.

## 0.5.0 (2026-10-29)

- Pestaña «Personalización»:
  - Portadas, fondos y logos de SteamGridDB para cualquier juego de la biblioteca, con selector visual y restaurar originales.
  - Temas de DeckThemes para CSS Loader: explorar por categoría, instalar, activar y quitar.
  - Videos de arranque propios (`.webm`).
  - Fondo de escritorio de KDE.

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
