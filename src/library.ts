import { callable } from "@decky/api";

declare const collectionStore: any;

declare const SteamClient: any;

const reportLibrary = callable<[any[], any[]], boolean>("report_library");
// Tipos de SteamAppOverview.app_type que interesan: juegos y accesos directos.
const GAME = 1;
const SHORTCUT = 1073741824;

// Envía al daemon el tiempo de juego de la biblioteca (Steam solo lo expone aquí,
// incluido el de los accesos directos de emuladores).
async function report() {
  const apps = collectionStore?.allAppsCollection?.allApps;
  if (!apps?.length) return;
  const hidden = new Set<number>((collectionStore.hiddenAppsCollection?.allApps ?? []).map((a: any) => a.appid));
  const list = apps
    .filter((a: any) => a.app_type === GAME || a.app_type === SHORTCUT)
    .map((a: any) => ({
      appid: a.appid,
      name: a.display_name,
      shortcut: a.app_type === SHORTCUT,
      minutes: a.minutes_playtime_forever ?? 0,
      minutes_2w: a.minutes_playtime_last_two_weeks ?? 0,
      last_played: a.rt_last_time_played ?? 0,
      installed: !!a.installed,
      hidden: hidden.has(a.appid),
      deck_compat: a.steam_deck_compat_category ?? 0,
    }));
  // Herramientas de compatibilidad (Proton) disponibles, para el detalle de cada juego.
  let tools: any[] = [];
  const sample = apps.find((a: any) => a.app_type === GAME && a.installed);
  if (sample && SteamClient?.Apps?.GetAvailableCompatTools) {
    try {
      tools = ((await SteamClient.Apps.GetAvailableCompatTools(sample.appid)) ?? []).map((t: any) => ({
        name: t.strToolName,
        display: t.strDisplayName,
      }));
    } catch {
      tools = [];
    }
  }
  await reportLibrary(list, tools);
}

const reportStoreUserdata = callable<[any], number>("report_store_userdata");

// Datos de la tienda con la sesión de Steam del cliente (no dependen de la privacidad
// del perfil): lista de deseados, ignorados, seguidos y etiquetas recomendadas.
export async function syncStoreUserdata() {
  const r = await fetch("https://store.steampowered.com/dynamicstore/userdata/", { credentials: "include" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const j = await r.json();
  return reportStoreUserdata({
    wishlist: j.rgWishlist ?? [],
    ignored: Object.keys(j.rgIgnoredApps ?? {}),
    followed: j.rgFollowedApps ?? [],
    recommended_tags: j.rgRecommendedTags ?? [],
    recommended_apps: j.rgRecommendedApps ?? [],
    owned: j.rgOwnedApps ?? [],
  });
}

export function startLibraryReport(): () => void {
  const run = () => report().catch((e) => console.error("DeckHub: tiempo de juego", e));
  const sync = () => syncStoreUserdata().catch((e) => console.error("DeckHub: datos de la tienda", e));
  const first = setTimeout(() => {
    run();
    sync();
  }, 10000);
  const id = setInterval(run, 2 * 60 * 1000);
  const syncId = setInterval(sync, 30 * 60 * 1000);
  return () => {
    clearTimeout(first);
    clearInterval(id);
    clearInterval(syncId);
  };
}
