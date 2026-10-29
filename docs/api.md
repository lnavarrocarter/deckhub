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

## Ajustes, partidas y trucos

| Método | Ruta | Cuerpo |
|---|---|---|
| GET/POST | `/api/settings` | `{steamgriddb_key?, auto_artwork?, backup_daily?, backup_keep?}` |
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
