# API HTTP

Base: `http://<ip-del-deck>:8765`. Respuestas JSON. Errores: `{"error": "..."}` con código 400/404/409/500.

## Autenticación

Rutas públicas (GET): `/`, `/api`, `/api/auth` y `/api/{system,storage,network,steam,services}`. Todo lo demás exige el token:

- Cabecera `X-DeckHub-Token: <token>`, o
- Cookie `deckhub_token`, que se fija con `POST /api/auth` `{"token": "..."}`.

El token está en `~/.config/deckhub/token` del Deck. Las rutas protegidas responden `{"ok": true, "data": ...}`.

## Estado

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api` | Todos los módulos de estado de una vez. |
| GET | `/api/{módulo}` | `system`, `storage`, `network`, `steam`, `services`. |
| GET/POST | `/api/auth` | Consultar / iniciar sesión con el token. |

## Unidades y archivos

| Método | Ruta | Cuerpo / query |
|---|---|---|
| POST | `/api/drives/mount` | `{device}` |
| POST | `/api/drives/unmount` | `{device}` |
| POST | `/api/drives/automount` | `{uuid, enabled}` |
| GET | `/api/files/roots` | |
| GET | `/api/files/list` | `?path=&hidden=1` |
| GET | `/api/files/download` | `?path=` |
| POST | `/api/files/mkdir` | `{path, name}` |
| POST | `/api/files/rename` | `{path, name}` |
| POST | `/api/files/trash` | `{paths: []}` |
| POST | `/api/files/copy`, `/api/files/move` | `{paths: [], dest}` → tarea |
| POST | `/api/files/upload` | multipart, `?dir=` |
| GET | `/api/space` | `?path=` |

## Paquetes, juegos y emuladores

| Método | Ruta | Cuerpo / query |
|---|---|---|
| GET | `/api/packages` | |
| GET | `/api/packages/search` | `?q=` |
| POST | `/api/packages/install`, `/api/packages/uninstall` | `{id}` |
| GET | `/api/roms` | `?refresh=1` |
| GET | `/api/emulators` | |
| POST | `/api/emulators/install`, `/api/emulators/configure` | `{id}` |
| POST | `/api/emulators/eden/firmware` | multipart (zip) o `{path}` → tarea |
| POST | `/api/emulators/eden/keys` | multipart `prod.keys` / `title.keys` |

## Ofertas

| Método | Ruta | Cuerpo / query |
|---|---|---|
| GET | `/api/store` | juegos seguidos, precios, mínimos, alertas |
| POST | `/api/store/import` | importa la lista de deseados de Steam |
| POST | `/api/store/refresh` | revisa precios ahora |
| GET | `/api/store/search` | `?q=` |
| POST | `/api/store/userdata` | datos de la tienda leídos por el plugin (deseados, ignorados, seguidos, etiquetas) |
| POST | `/api/store/track` | `{appid, target?, notify_low?}` (`target` en centavos) |
| POST | `/api/store/untrack` | `{appid}` |
| GET | `/api/store/notifications` | alertas pendientes (las entrega el plugin) |
| POST | `/api/store/notifications/ack` | `{id}` |

`/api/settings` acepta también `store_country` (código de 2 letras) e `itad_key`.

## Biblioteca

| Método | Ruta | Cuerpo / query |
|---|---|---|
| GET | `/api/library` | juegos de Steam, ROMs y accesos directos + versiones de Proton |
| GET | `/api/library/detail` | `?key=steam:<appid>\|rom:<ruta>\|sc:<appid>` |
| POST | `/api/library/action` | `{action: run\|launch_options\|shortcut_launch_options\|compat_tool\|hidden, appid, value?}` |
| GET | `/api/custom/art/image` | `?appid=&kind=`: imagen actual (para `<img>`) |

## Accesos directos y portadas

| Método | Ruta | Cuerpo |
|---|---|---|
| GET | `/api/shortcuts` | |
| POST | `/api/shortcuts/add`, `/api/shortcuts/remove` | `{paths: []}` |
| GET | `/api/shortcuts/pending` | cola para el plugin |
| POST | `/api/shortcuts/ack` | `{key, appid?, removed?, error?}` |
| GET | `/api/shortcuts/art/pending` | |
| POST | `/api/shortcuts/art/ack` | `{key, error?}` |
| POST | `/api/shortcuts/art/refresh` | `{paths?}` (vacío = todas) |

## Personalización

| Método | Ruta | Cuerpo / query |
|---|---|---|
| GET | `/api/custom` | videos, fondos, temas instalados y estado de CSS Loader |
| GET | `/api/custom/art/options` | `?appid=&kind=grid\|wide\|hero\|logo&title=&shortcut=1` |
| GET | `/api/custom/art/current` | `?appid=` o `?appids=1,2,3`: imagen actual de cada tipo (personalizada u original) |
| POST | `/api/custom/art/apply` | `{appid, kind, url}` (solo URLs de SteamGridDB) |
| POST | `/api/custom/art/reset` | `{appid, kinds?}` |
| POST | `/api/custom/movies/upload` | multipart `.webm` |
| POST | `/api/custom/movies/default` | `{name}` o `{name: null}` |
| POST | `/api/custom/movies/delete` | `{name}` |
| POST | `/api/custom/wallpaper/upload` | multipart imagen |
| POST | `/api/custom/wallpaper/set` | `{path}` |
| GET | `/api/custom/preview` | `?path=` (fondos, videos e imágenes de la biblioteca) |
| GET | `/api/custom/movies/browse` | `?search=&sort=trending\|downloads-desc\|likes-desc\|created_at-desc&page=` (steamdeckrepo.com) |
| POST | `/api/custom/movies/download` | `{video, slug}` |
| GET | `/api/custom/wallpaper/browse` | `?q=&page=` (Wallhaven, solo SFW) |
| POST | `/api/custom/wallpaper/download` | `{url, apply?}` |
| GET | `/api/custom/themes/browse` | `?search=&target=&page=` |
| POST | `/api/custom/themes/install` | `{id}` (DeckThemes) |
| POST | `/api/custom/themes/toggle` | `{folder, active}` |
| POST | `/api/custom/themes/remove` | `{folder}` |
| POST | `/api/decky/install` | `{name}`: instala un plugin de la tienda de Decky (confirmación en el Deck) |
| GET | `/api/decky/actions/pending` | acciones para el plugin (`install`, `css_install`, `css_state`, `css_reset`) |
| POST | `/api/decky/actions/ack` | `{id}` |

## Ajustes, partidas y trucos

| Método | Ruta | Cuerpo |
|---|---|---|
| GET/POST | `/api/settings` | `{steamgriddb_key?, auto_artwork?, backup_daily?, backup_keep?, lan_access?}`; cambiar `lan_access` reinicia el daemon (`restarting: true`) |
| GET | `/api/steam/playtime` | tiempo de juego de la biblioteca |
| POST | `/api/steam/playtime` | `{apps: []}` (lo envía el plugin) |
| GET | `/api/saves` | |
| POST | `/api/saves/backup` | `{emulator, only?}` |
| POST | `/api/saves/restore` | `{name, emulator}` |
| POST | `/api/saves/migrate` | yuzu → Eden |
| GET | `/api/cheats` | |
| POST | `/api/cheats/ps2/save` | `{path, text}` |
| POST | `/api/cheats/ps2/toggle` | `{path, enabled}` |
| POST | `/api/cheats/ps2/delete` | `{path}` |
| POST | `/api/cheats/eden/save` | `{title_id, name, build_id, text}` |
| POST | `/api/cheats/eden/toggle` | `{title_id, name, enabled}` |
| POST | `/api/cheats/eden/delete` | `{title_id, name}` |
| GET | `/api/jobs` | tareas y progreso |
