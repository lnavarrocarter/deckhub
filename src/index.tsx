import { ButtonItem, Field, PanelSection, PanelSectionRow, ToggleField, staticClasses } from "@decky/ui";
import { callable, definePlugin, toaster } from "@decky/api";
import { useEffect, useState } from "react";
import { FaHeartbeat } from "react-icons/fa";
import { downloadAll, pendingDownloads, startDownloads } from "./downloads";
import { startLibraryReport } from "./library";
import { startShortcutSync } from "./shortcuts";

type Status = { ok: true; data: any } | { ok: false; error: string };

const getStatus = callable<[], Status>("get_status");
type AccessInfo = { url: string; token: string; lan_access: boolean | null };
const getAccess = callable<[], AccessInfo>("get_access");
const setLanAccess = callable<[boolean], { ok: boolean; error?: string }>("set_lan_access");
const restartDaemon = callable<[], { ok: boolean; error?: string }>("restart_daemon");
const setMounted = callable<[string, boolean], { ok: boolean; error?: string }>("set_mounted");

// Actualizaciones de Steam en espera, con «Descargar todo».
function Downloads() {
  const [n, setN] = useState(pendingDownloads().filter((i) => !i.active && i.queue_index < 0).length);
  useEffect(() => {
    const id = setInterval(() => setN(pendingDownloads().filter((i) => !i.active && i.queue_index < 0).length), 3000);
    return () => clearInterval(id);
  }, []);
  if (!n) return null;
  return (
    <PanelSection title="Descargas">
      <PanelSectionRow>
        <ButtonItem
          layout="below"
          onClick={async () => {
            const c = await downloadAll();
            toaster.toast({ title: "DeckHub · Descargas", body: `${c} descargas en cola` });
          }}
        >
          Descargar todo ({n})
        </ButtonItem>
      </PanelSectionRow>
    </PanelSection>
  );
}

// Dirección del panel web y token, para entrar desde el PC o el móvil.
function Access() {
  const [access, setAccess] = useState<AccessInfo | null>(null);
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    getAccess().then(setAccess);
  }, []);

  const toggle = async (on: boolean) => {
    setBusy(true);
    const r = await setLanAccess(on);
    toaster.toast({
      title: "DeckHub",
      body: r.ok ? (on ? "Panel abierto a la red (puerto 8765)" : "Panel solo accesible desde el Deck") : r.error ?? "Error",
    });
    // El daemon se reinicia para escuchar en la nueva dirección.
    setTimeout(async () => {
      setAccess(await getAccess());
      setBusy(false);
    }, 5000);
  };

  return (
    <PanelSection title="Panel web">
      <PanelSectionRow>
        <ToggleField
          label="Acceso desde la red"
          description="Puerto 8765 para el PC o el móvil"
          checked={access?.lan_access ?? false}
          disabled={busy || access?.lan_access == null}
          onChange={toggle}
        />
      </PanelSectionRow>
      {access?.lan_access && (
        <PanelSectionRow>
          <Field label="Dirección" bottomSeparator="none">
            {access.url}
          </Field>
        </PanelSectionRow>
      )}
      <PanelSectionRow>
        {show ? (
          <Field label="Token" description={access?.token || "aún no generado"} bottomSeparator="none" />
        ) : (
          <ButtonItem layout="below" onClick={() => setShow(true)}>
            Mostrar token
          </ButtonItem>
        )}
      </PanelSectionRow>
    </PanelSection>
  );
}

// Particiones de tarjetas SD/USB que se pueden montar (se omiten las de sistema, <1 GB).
function Drives({ disks }: { disks: any[] }) {
  const [busy, setBusy] = useState<string | null>(null);
  const parts = disks
    .filter((d) => d.removable)
    .flatMap((d) => d.partitions)
    .filter((p: any) => p.mountable && p.size > 1e9);
  if (!parts.length) return null;

  const toggle = async (p: any, on: boolean) => {
    setBusy(p.path);
    const r = await setMounted(p.path, on);
    setBusy(null);
    toaster.toast({
      title: "DeckHub",
      body: r.ok ? `${p.label ?? p.name} ${on ? "montada" : "desmontada"}` : r.error ?? "Error",
    });
  };

  return (
    <PanelSection title="Unidades">
      {parts.map((p: any) => (
        <PanelSectionRow key={p.path}>
          <ToggleField
            label={p.label ?? p.name}
            description={`${p.fstype} · ${gb(p.size)}${p.used != null ? ` · ${gb(p.used)} usados` : ""}`}
            checked={!!p.mountpoint}
            disabled={busy === p.path}
            onChange={(on) => toggle(p, on)}
          />
        </PanelSectionRow>
      ))}
    </PanelSection>
  );
}

const gb = (b?: number) =>
  b == null ? "—" : b >= 1e12 ? `${(b / 1e12).toFixed(2)} TB` : `${(b / 1e9).toFixed(1)} GB`;
const v = (x: unknown, unit = "") => (x == null ? "—" : `${x}${unit}`);

function Content() {
  const [status, setStatus] = useState<Status | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      const s = await getStatus();
      if (alive) setStatus(s);
    };
    tick();
    const id = setInterval(tick, 2000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  if (!status) return <PanelSection title="DeckHub">Cargando…</PanelSection>;
  if (!status.ok)
    return (
      <PanelSection title="DeckHub">
        <PanelSectionRow>
          <Field label="Daemon no disponible" description={status.error} />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            onClick={async () => {
              const r = await restartDaemon();
              toaster.toast({ title: "DeckHub", body: r.ok ? "Daemon reiniciado" : r.error ?? "Error" });
            }}
          >
            Reiniciar daemon
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
    );

  const { system: s, storage: st, network: n, steam: sm } = status.data;
  const home = st.mounts?.find((m: any) => m.mountpoint === "/home");

  return (
    <>
      <PanelSection title="Sistema">
        <PanelSectionRow>
          <Field label="CPU" bottomSeparator="none">
            {v(s.cpu?.percent, "%")} · {v(s.cpu?.temp, " °C")}
          </Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field label="GPU" bottomSeparator="none">
            {v(s.gpu?.percent, "%")} · {v(s.gpu?.mhz, " MHz")} · {v(s.gpu?.temp, " °C")}
          </Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field label="Consumo / TDP" bottomSeparator="none">
            {v(s.gpu?.watts, " W")} / {v(s.tdp?.watts, " W")}
          </Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field label="RAM" bottomSeparator="none">
            {gb(s.memory?.used)} / {gb(s.memory?.total)}
          </Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field label="Ventilador" bottomSeparator="none">
            {v(s.fan_rpm, " RPM")}
          </Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field label="Batería" bottomSeparator="none">
            {v(s.battery?.percent, "%")} · {s.battery?.status ?? "—"} · {v(s.battery?.watts, " W")}
          </Field>
        </PanelSectionRow>
      </PanelSection>

      <Downloads />

      <Drives disks={st.disks ?? []} />

      <PanelSection title="Almacenamiento y red">
        <PanelSectionRow>
          <Field label="/home" bottomSeparator="none">
            {home ? `${gb(home.free)} libres (${home.percent}%)` : "—"}
          </Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field label="WiFi" bottomSeparator="none">
            {n.wifi ? `${n.wifi.ssid} · ${n.wifi.signal}%` : "desconectado"}
          </Field>
        </PanelSectionRow>
      </PanelSection>

      <Access />

      <PanelSection title="Steam">
        <PanelSectionRow>
          <Field label="Jugando" bottomSeparator="none">
            {sm.running ? sm.running.name ?? `AppID ${sm.running.appid}` : "nada"}
          </Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field label="Instalados" bottomSeparator="none">
            {sm.games?.length ?? 0} · {gb(sm.total_size)}
          </Field>
        </PanelSectionRow>
      </PanelSection>
    </>
  );
}

export default definePlugin(() => {
  const stopSync = startShortcutSync();
  const stopLibrary = startLibraryReport();
  const stopDownloads = startDownloads();
  return {
    name: "DeckHub",
    titleView: <div className={staticClasses.Title}>DeckHub</div>,
    content: <Content />,
    icon: <FaHeartbeat />,
    onDismount: () => {
      stopSync();
      stopLibrary();
      stopDownloads();
    },
  };
});
