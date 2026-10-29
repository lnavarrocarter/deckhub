// Aplica la cola de accesos directos del daemon usando la API interna de Steam.
// Corre mientras Decky esté cargado, no solo con el panel abierto.
import { callable, toaster } from "@decky/api";

declare const SteamClient: any;
declare const appStore: any;
declare const collectionStore: any;

type Pending = {
  key: string;
  title: string;
  exe: string;
  start_dir: string;
  launch_options: string;
  collection: string;
  appid: number | null;
  status: "pending_add" | "pending_remove";
};

type PendingArt = {
  key: string;
  appid: number;
  images: { asset: number; ext: string; data: string }[];
  reset: number[]; // tipos de imagen a devolver a la original de Steam
};

const getPending = callable<[], Pending[]>("get_pending_shortcuts");
const ack = callable<[string, number | null, boolean, string | null], boolean>("ack_shortcut");
const getPendingArt = callable<[], PendingArt[]>("get_pending_art");
const ackArt = callable<[string, string | null], boolean>("ack_art");

async function applyArt() {
  const items = await getPendingArt();
  for (const item of items) {
    try {
      for (const asset of item.reset ?? []) {
        await SteamClient.Apps.ClearCustomArtworkForApp(item.appid, asset);
      }
      for (const img of item.images) {
        await SteamClient.Apps.SetCustomArtworkForApp(item.appid, img.data, img.ext, img.asset);
      }
      await ackArt(item.key, null);
    } catch (e: any) {
      await ackArt(item.key, String(e?.message ?? e));
    }
  }
  return items.length;
}

type DeckyAction =
  | { id: string; type: "install"; name: string; version: string; hash: string; artifact: string }
  | { id: string; type: "css_reset" }
  | { id: string; type: "css_install"; name: string; theme_id: string; deps: number }
  | { id: string; type: "css_state"; name: string; active: boolean };

const DECKTHEMES = "https://api.deckthemes.com/";

// CSS Loader usa la API antigua de Decky (sin api_version).
function cssLoader(method: string, args: Record<string, unknown> = {}) {
  return (window as any).DeckyBackend.call("loader/call_legacy_plugin_method", "CSS Loader", method, args);
}

// La interfaz de CSS Loader guarda su propia lista de temas: se recarga su frontend
// (como hace Decky al actualizar un plugin) para que muestre los cambios.
async function refreshCssLoaderUI() {
  const loader = (window as any).DeckyPluginLoader;
  const p = loader?.plugins?.find((x: any) => x.name === "CSS Loader");
  if (p) await loader.importPlugin(p.name, p.version, p.loadType);
}
const getPendingActions = callable<[], DeckyAction[]>("get_pending_actions");
const ackAction = callable<[string], boolean>("ack_action");

// Acciones pedidas desde el panel web que solo se pueden hacer dentro de Decky:
// instalar un plugin (con las mismas llamadas que la tienda, que pide confirmación
// en pantalla) y recargar CSS Loader tras cambiar temas.
async function applyActions() {
  const items = await getPendingActions();
  const backend = (window as any).DeckyBackend;
  if (!items.length || !backend?.call) return;
  let cssChanged = false;
  for (const a of items) {
    await ackAction(a.id); // antes, para no repetirla si Decky se recarga
    try {
      if (a.type === "install") {
        await backend.call("utilities/install_plugin", a.artifact, a.name, a.version, a.hash, 0 /* INSTALL */);
      } else if (a.type === "css_reset") {
        await cssLoader("reset");
        cssChanged = true;
      } else if (a.type === "css_install") {
        // El instalador de CSS Loader trae también las dependencias (temas de un perfil).
        await cssLoader("download_theme_from_url", { id: a.theme_id, url: DECKTHEMES });
        await cssLoader("reset");
        await cssLoader("set_theme_state", { name: a.name, state: true });
        toaster.toast({
          title: "DeckHub · Temas",
          body: a.deps ? `${a.name} instalado con ${a.deps} temas` : `${a.name} instalado`,
        });
        cssChanged = true;
      } else if (a.type === "css_state") {
        await cssLoader("set_theme_state", { name: a.name, state: a.active });
        cssChanged = true;
      }
    } catch (e: any) {
      toaster.toast({ title: "DeckHub", body: `Acción ${a.type} falló: ${e?.message ?? e}` });
    }
  }
  if (cssChanged) await refreshCssLoaderUI().catch((e) => console.warn("DeckHub: CSS Loader", e));
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function overview(appid: number) {
  // El overview tarda un momento en existir tras crear el acceso directo.
  for (let i = 0; i < 20; i++) {
    const ov = appStore.GetAppOverviewByAppID(appid);
    if (ov) return ov;
    await sleep(250);
  }
  return null;
}

async function addToCollection(name: string, appid: number) {
  const ov = await overview(appid);
  if (!ov || typeof collectionStore === "undefined") return;
  let col = collectionStore.userCollections?.find((c: any) => c.displayName === name);
  if (!col) {
    col = collectionStore.NewUnsavedCollection(name, undefined, [ov]);
  } else {
    col.AsDragDropCollection().AddApps([ov]);
  }
  await col.Save();
}

async function add(p: Pending) {
  // Si ya existe (p. ej. se reintenta), no se duplica.
  if (p.appid && appStore.GetAppOverviewByAppID(p.appid)) return p.appid;
  const appid: number = await SteamClient.Apps.AddShortcut(p.title, p.exe, p.start_dir, p.launch_options);
  // AddShortcut a veces ignora nombre y opciones: se fijan explícitamente.
  SteamClient.Apps.SetShortcutName(appid, p.title);
  SteamClient.Apps.SetShortcutExe(appid, `"${p.exe}"`);
  SteamClient.Apps.SetShortcutStartDir(appid, p.start_dir);
  SteamClient.Apps.SetShortcutLaunchOptions(appid, p.launch_options);
  try {
    await addToCollection(p.collection, appid);
  } catch (e) {
    console.warn("DeckHub: no se pudo añadir a la colección", e);
  }
  return appid;
}

let running = false;

export async function syncShortcuts() {
  if (running) return;
  running = true;
  try {
    const items = await getPending();
    let added = 0;
    let removed = 0;
    for (const p of items) {
      try {
        if (p.status === "pending_add") {
          await ack(p.key, await add(p), false, null);
          added++;
        } else {
          if (p.appid) SteamClient.Apps.RemoveShortcut(p.appid);
          await ack(p.key, null, true, null);
          removed++;
        }
      } catch (e: any) {
        await ack(p.key, null, false, String(e?.message ?? e));
      }
    }
    const art = await applyArt();
    await applyActions();
    if (added || removed || art) {
      const parts = [
        added && `${added} juegos añadidos`,
        removed && `${removed} quitados`,
        art && `${art} portadas`,
      ].filter(Boolean);
      toaster.toast({ title: "DeckHub · Steam", body: parts.join(", ") });
    }
  } finally {
    running = false;
  }
}

export function startShortcutSync(intervalMs = 5000) {
  syncShortcuts();
  const id = setInterval(syncShortcuts, intervalMs);
  return () => clearInterval(id);
}
