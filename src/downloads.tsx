// «Descargar todo»: pone en cola e inicia todas las actualizaciones pendientes de la
// página de Descargas de Steam (las programadas para más tarde incluidas).
import { callable, routerHook, toaster } from "@decky/api";
import { DialogButton, Focusable } from "@decky/ui";
import { useEffect, useState } from "react";

declare const SteamClient: any;
declare const appStore: any;

const reportDownloads = callable<[any[]], boolean>("report_downloads");
const ROUTE = "/library/downloads";

let items: any[] = [];

// Steam agrupa la cola por equipo: "0" es este Deck; el resto, otros PCs conectados
// (Descargas remotas). downloadsStore lo guarda como mapa y el callback como lista
// de {remote_client_id, item_data}. Solo interesa la cola local.
function localItems(src: any): any[] {
  if (src && typeof src.get === "function" && !Array.isArray(src)) return Array.from(src.get("0") ?? []);
  const list = Array.from(src ?? []) as any[];
  const local = list.find((e) => String(e?.remote_client_id) === "0");
  if (local) return local.item_data ?? [];
  return list.filter((e) => e?.appid);
}

function pendingBytes(i: any) {
  return (i.update_type_info ?? [])
    .filter((u: any) => u.has_update && !u.completed)
    .flatMap((u: any) => u.progress ?? [])
    .reduce((n: number, p: any) => n + Math.max(0, (p.bytes_total ?? 0) - (p.bytes_in_progress ?? 0)), 0);
}

export function pendingDownloads() {
  return items.filter((i) => !i.completed && (i.update_type_info ?? []).some((u: any) => u.has_update && !u.completed));
}

// Igual que los botones de Steam: cada llamada lleva el equipo ("0" = este Deck).
// QueueAppUpdate también adelanta las programadas para la ventana de actualizaciones.
const LOCAL = "0";

export async function downloadAll() {
  const list = pendingDownloads().filter((i) => !i.active);
  SteamClient.Downloads.EnableAllDownloads(true, LOCAL);
  for (const i of list) {
    if (i.queue_index < 0) await SteamClient.Downloads.QueueAppUpdate(i.appid, LOCAL);
    if (i.paused) await SteamClient.Downloads.ResumeAppUpdate(i.appid, LOCAL);
  }
  return list.length;
}

const gb = (b: number) => (b >= 1e9 ? `${(b / 1e9).toFixed(1)} GB` : `${Math.round(b / 1e6)} MB`);

function report() {
  reportDownloads(
    items.map((i) => ({
      appid: i.appid,
      name: appStore.GetAppOverviewByAppID(i.appid)?.display_name ?? String(i.appid),
      active: !!i.active,
      paused: !!i.paused,
      queued: i.queue_index >= 0,
      completed: !!i.completed,
      deferred_time: i.deferred_time ?? 0,
      bytes: pendingBytes(i),
    })),
  ).catch(() => {});
}

function DownloadAllBar() {
  const [list, setList] = useState(pendingDownloads());
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const id = setInterval(() => setList(pendingDownloads()), 2000);
    return () => clearInterval(id);
  }, []);
  const waiting = list.filter((i) => !i.active && i.queue_index < 0);
  if (!waiting.length) return null;
  const total = waiting.reduce((n, i) => n + pendingBytes(i), 0);
  return (
    <Focusable style={{ display: "flex", alignItems: "center", gap: "12px", padding: "16px 24px 24px" }}>
      <DialogButton
        style={{ width: "auto", minWidth: "220px" }}
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          const n = await downloadAll();
          toaster.toast({ title: "DeckHub · Descargas", body: `${n} descargas en cola` });
          setBusy(false);
        }}
      >
        Descargar todo ({waiting.length})
      </DialogButton>
      <span style={{ opacity: 0.7 }}>{gb(total)} pendientes · DeckHub</span>
    </Focusable>
  );
}

export function startDownloads(): () => void {
  items = localItems((window as any).downloadsStore?.m_DownloadItems);
  let timer: any = null;
  const reg = SteamClient.Downloads.RegisterForDownloadItems((_active: boolean, list: any[]) => {
    items = localItems(list);
    clearTimeout(timer);
    timer = setTimeout(report, 1500); // el callback llega varias veces por segundo durante una descarga
  });
  setTimeout(report, 3000);
  const patch = routerHook.addPatch(ROUTE, (props: any) => {
    const original = props.children;
    props.children = (
      <>
        {original}
        <DownloadAllBar />
      </>
    );
    return props;
  });
  return () => {
    reg?.unregister?.();
    clearTimeout(timer);
    routerHook.removePatch(ROUTE, patch);
  };
}
