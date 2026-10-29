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
};

const getPending = callable<[], Pending[]>("get_pending_shortcuts");
const ack = callable<[string, number | null, boolean, string | null], boolean>("ack_shortcut");
const getPendingArt = callable<[], PendingArt[]>("get_pending_art");
const ackArt = callable<[string, string | null], boolean>("ack_art");

async function applyArt() {
  const items = await getPendingArt();
  for (const item of items) {
    try {
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
