import { Field, PanelSection, PanelSectionRow, ToggleField, staticClasses } from "@decky/ui";
import { callable, definePlugin, toaster } from "@decky/api";
import { useEffect, useState } from "react";
import { FaHeartbeat } from "react-icons/fa";
import { startShortcutSync } from "./shortcuts";

type Status = { ok: true; data: any } | { ok: false; error: string };

const getStatus = callable<[], Status>("get_status");
const getDashboardUrl = callable<[], string>("get_dashboard_url");
const setMounted = callable<[string, boolean], { ok: boolean; error?: string }>("set_mounted");

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
  const [url, setUrl] = useState("");

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      const s = await getStatus();
      if (alive) setStatus(s);
    };
    tick();
    getDashboardUrl().then((u) => alive && setUrl(u));
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
        <PanelSectionRow>
          <Field label="Panel web" description={url} bottomSeparator="none" />
        </PanelSectionRow>
      </PanelSection>

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
  return {
    name: "DeckHub",
    titleView: <div className={staticClasses.Title}>DeckHub</div>,
    content: <Content />,
    icon: <FaHeartbeat />,
    onDismount: stopSync,
  };
});
