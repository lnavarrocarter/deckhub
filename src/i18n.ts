// Textos del plugin en cada idioma. El idioma sale del daemon (el elegido en el panel o,
// en automático, el de Steam) y, si no responde, del propio Steam.
import { callable } from "@decky/api";

declare const SteamClient: any;

const STRINGS = {
  es: {
    loading: "Cargando…",
    daemonDown: "El servicio de DeckHub no responde",
    restartDaemon: "Reiniciar servicio",
    daemonRestarted: "Servicio reiniciado",
    system: "Sistema",
    battery: "Batería",
    powerTdp: "Consumo / TDP",
    fan: "Ventilador",
    downloads: "Descargas",
    downloadAll: "Descargar todo ({n})",
    queued: "{n} descargas en cola",
    noDownloads: "No hay descargas pendientes",
    pendingSize: "{size} pendientes",
    dashboard: "Panel web",
    networkAccess: "Acceso desde la red",
    networkAccessDesc: "Para abrir el panel desde el PC o el móvil (puerto 8765)",
    scanQr: "Escanea con el móvil o abre en el navegador:",
    openHere: "Abrir el panel en el Deck",
    showToken: "Mostrar token",
    token: "Token",
    tokenMissing: "aún no generado",
    lanOn: "Panel abierto a la red (puerto 8765)",
    lanOff: "Panel solo accesible desde el Deck",
    drives: "Unidades",
    mounted: "{name} montada",
    unmounted: "{name} desmontada",
    used: "{size} usados",
    steam: "Steam",
    playing: "Jugando",
    nothing: "nada",
    installed: "Instalados",
    storage: "/home",
    free: "{size} libres ({pct}%)",
    wifi: "WiFi",
    disconnected: "desconectado",
    error: "Error",
    themes: "Temas",
    themeInstalled: "{name} instalado",
    themeInstalledDeps: "{name} instalado con {n} temas",
    deals: "Ofertas",
    wishlistSynced: "Lista de deseados sincronizada",
    wishlistSyncedNew: "Lista de deseados sincronizada ({n} nuevos)",
    actionFailed: "Acción {type} falló: {msg}",
    gamesAdded: "{n} juegos añadidos",
    gamesRemoved: "{n} quitados",
    artApplied: "{n} portadas",
    alertTarget: "Bajó de tu precio objetivo",
    alertLow: "Está en su mínimo histórico",
    alertBoth: "Bajó de tu precio objetivo y está en su mínimo histórico",
    performance: "Rendimiento",
    memoryTuning: "Memoria optimizada",
    tuningValue: "{done} de {total} · swap {swap} GB",
    applyRecommended: "Aplicar recomendados",
    tuningApplied: "Ajustes de memoria aplicados",
    helperMissing: "Instala el ayudante desde el panel web (Rendimiento)",
    updateAvailable: "Nueva versión {v} disponible",
    updateNow: "Actualizar DeckHub",
    updateConfirm: "Confirma la actualización en la ventana de Decky",
  },
  en: {
    loading: "Loading…",
    daemonDown: "The DeckHub service is not responding",
    restartDaemon: "Restart service",
    daemonRestarted: "Service restarted",
    system: "System",
    battery: "Battery",
    powerTdp: "Power / TDP",
    fan: "Fan",
    downloads: "Downloads",
    downloadAll: "Download all ({n})",
    queued: "{n} downloads queued",
    noDownloads: "No pending downloads",
    pendingSize: "{size} pending",
    dashboard: "Web dashboard",
    networkAccess: "Network access",
    networkAccessDesc: "To open the dashboard from your PC or phone (port 8765)",
    scanQr: "Scan with your phone or open in a browser:",
    openHere: "Open the dashboard on the Deck",
    showToken: "Show token",
    token: "Token",
    tokenMissing: "not generated yet",
    lanOn: "Dashboard open to the network (port 8765)",
    lanOff: "Dashboard only reachable from the Deck",
    drives: "Drives",
    mounted: "{name} mounted",
    unmounted: "{name} unmounted",
    used: "{size} used",
    steam: "Steam",
    playing: "Playing",
    nothing: "nothing",
    installed: "Installed",
    storage: "/home",
    free: "{size} free ({pct}%)",
    wifi: "Wi-Fi",
    disconnected: "disconnected",
    error: "Error",
    themes: "Themes",
    themeInstalled: "{name} installed",
    themeInstalledDeps: "{name} installed with {n} themes",
    deals: "Deals",
    wishlistSynced: "Wishlist synced",
    wishlistSyncedNew: "Wishlist synced ({n} new)",
    actionFailed: "Action {type} failed: {msg}",
    gamesAdded: "{n} games added",
    gamesRemoved: "{n} removed",
    artApplied: "{n} artworks",
    alertTarget: "Dropped below your target price",
    alertLow: "Is at its historical low",
    alertBoth: "Dropped below your target price and is at its historical low",
    performance: "Performance",
    memoryTuning: "Memory tuning",
    tuningValue: "{done} of {total} · swap {swap} GB",
    applyRecommended: "Apply recommended",
    tuningApplied: "Memory settings applied",
    helperMissing: "Install the helper from the web dashboard (Performance)",
    updateAvailable: "New version {v} available",
    updateNow: "Update DeckHub",
    updateConfirm: "Confirm the update in Decky's window",
  },
};

type Key = keyof typeof STRINGS.es;
type Lang = keyof typeof STRINGS;
let lang: Lang = "en";

const getLanguage = callable<[], string | null>("get_language");
const STEAM_LANGS: Record<string, Lang> = { spanish: "es", latam: "es", english: "en" };

export async function initLanguage() {
  let code = await getLanguage().catch(() => null);
  if (!code) {
    try {
      code = STEAM_LANGS[(await SteamClient.Settings.GetCurrentLanguage()) ?? ""] ?? "en";
    } catch {
      code = "en";
    }
  }
  lang = (code in STRINGS ? code : "en") as Lang;
}

export function t(key: Key, vars: Record<string, string | number> = {}) {
  const s: string = STRINGS[lang][key] ?? STRINGS.en[key];
  return s.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ""));
}
