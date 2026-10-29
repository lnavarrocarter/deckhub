import { ButtonItem, Field, Navigation, PanelSection, PanelSectionRow, ToggleField, staticClasses } from "@decky/ui";
import { callable, definePlugin, toaster } from "@decky/api";
import { useEffect, useState } from "react";
import { FaHeartbeat } from "react-icons/fa";
import qrcode from "qrcode-generator";
import { downloadAll, pendingDownloads, startDownloads } from "./downloads";
import { initLanguage, t } from "./i18n";
import { startLibraryReport } from "./library";
import { startShortcutSync } from "./shortcuts";

type Status = { ok: true; data: any } | { ok: false; error: string };

const getStatus = callable<[], Status>("get_status");
type AccessInfo = { url: string; token: string; lan_access: boolean | null };
const getAccess = callable<[], AccessInfo>("get_access");
const setLanAccess = callable<[boolean], { ok: boolean; error?: string }>("set_lan_access");
const restartDaemon = callable<[], { ok: boolean; error?: string }>("restart_daemon");
const setMounted = callable<[string, boolean], { ok: boolean; error?: string }>("set_mounted");

const gb = (b?: number) =>
  b == null ? "—" : b >= 1e12 ? `${(b / 1e12).toFixed(2)} TB` : `${(b / 1e9).toFixed(1)} GB`;
const v = (x: unknown, unit = "") => (x == null ? "—" : `${x}${unit}`);

// Código QR de la dirección del panel, para abrirlo desde el móvil sin teclear.
function QrCode({ text }: { text: string }) {
  const qr = qrcode(0, "M");
  qr.addData(text);
  qr.make();
  return (
    <div
      style={{ background: "#fff", padding: "8px", borderRadius: "6px", width: "fit-content", margin: "0 auto" }}
      dangerouslySetInnerHTML={{ __html: qr.createSvgTag({ cellSize: 4, margin: 0 }) }}
    />
  );
}

// Actualizaciones de Steam en espera, con «Descargar todo».
function Downloads() {
  const waiting = () => pendingDownloads().filter((i) => !i.active && i.queue_index < 0).length;
  const [n, setN] = useState(waiting());
  useEffect(() => {
    const id = setInterval(() => setN(waiting()), 3000);
    return () => clearInterval(id);
  }, []);
  if (!n) return null;
  return (
    <PanelSection title={t("downloads")}>
      <PanelSectionRow>
        <ButtonItem
          layout="below"
          onClick={async () => {
            const c = await downloadAll();
            toaster.toast({ title: `DeckHub · ${t("downloads")}`, body: t("queued", { n: c }) });
          }}
        >
          {t("downloadAll", { n })}
        </ButtonItem>
      </PanelSectionRow>
    </PanelSection>
  );
}

// Panel web: abrirlo en el Deck, o desde el PC/móvil con el QR y el token.
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
    toaster.toast({ title: "DeckHub", body: r.ok ? t(on ? "lanOn" : "lanOff") : r.error ?? t("error") });
    // El daemon se reinicia para escuchar en la nueva dirección.
    setTimeout(async () => {
      setAccess(await getAccess());
      setBusy(false);
    }, 5000);
  };

  return (
    <PanelSection title={t("dashboard")}>
      <PanelSectionRow>
        <ButtonItem layout="below" onClick={() => Navigation.NavigateToExternalWeb("http://127.0.0.1:8765")}>
          {t("openHere")}
        </ButtonItem>
      </PanelSectionRow>
      <PanelSectionRow>
        <ToggleField
          label={t("networkAccess")}
          description={t("networkAccessDesc")}
          checked={access?.lan_access ?? false}
          disabled={busy || access?.lan_access == null}
          onChange={toggle}
        />
      </PanelSectionRow>
      {access?.lan_access && access.url && (
        <PanelSectionRow>
          <Field label={t("scanQr")} description={access.url} bottomSeparator="none" />
          <QrCode text={access.url} />
        </PanelSectionRow>
      )}
      <PanelSectionRow>
        {show ? (
          <Field label={t("token")} description={access?.token || t("tokenMissing")} bottomSeparator="none" />
        ) : (
          <ButtonItem layout="below" onClick={() => setShow(true)}>
            {t("showToken")}
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
    const name = p.label ?? p.name;
    toaster.toast({ title: "DeckHub", body: r.ok ? t(on ? "mounted" : "unmounted", { name }) : r.error ?? t("error") });
  };

  return (
    <PanelSection title={t("drives")}>
      {parts.map((p: any) => (
        <PanelSectionRow key={p.path}>
          <ToggleField
            label={p.label ?? p.name}
            description={`${p.fstype} · ${gb(p.size)}${p.used != null ? ` · ${t("used", { size: gb(p.used) })}` : ""}`}
            checked={!!p.mountpoint}
            disabled={busy === p.path}
            onChange={(on) => toggle(p, on)}
          />
        </PanelSectionRow>
      ))}
    </PanelSection>
  );
}

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

  if (!status) return <PanelSection title="DeckHub">{t("loading")}</PanelSection>;
  if (!status.ok)
    return (
      <PanelSection title="DeckHub">
        <PanelSectionRow>
          <Field label={t("daemonDown")} description={status.error} />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            onClick={async () => {
              const r = await restartDaemon();
              toaster.toast({ title: "DeckHub", body: r.ok ? t("daemonRestarted") : r.error ?? t("error") });
            }}
          >
            {t("restartDaemon")}
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
    );

  const { system: s, storage: st, network: n, steam: sm } = status.data;
  const home = st.mounts?.find((m: any) => m.mountpoint === "/home");

  return (
    <>
      <PanelSection title={t("system")}>
        <PanelSectionRow>
          <Field label="CPU · GPU" bottomSeparator="none">
            {v(s.cpu?.percent, "%")} · {v(s.gpu?.percent, "%")} · {v(s.cpu?.temp, " °C")}
          </Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field label={t("battery")} bottomSeparator="none">
            {v(s.battery?.percent, "%")} · {v(s.battery?.watts, " W")}
          </Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field label={t("powerTdp")} bottomSeparator="none">
            {v(s.gpu?.watts, " W")} / {v(s.tdp?.watts, " W")} · {t("fan")} {v(s.fan_rpm, " RPM")}
          </Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field label="RAM · /home" bottomSeparator="none">
            {gb(s.memory?.used)} / {gb(s.memory?.total)} · {home ? t("free", { size: gb(home.free), pct: home.percent }) : "—"}
          </Field>
        </PanelSectionRow>
      </PanelSection>

      <Downloads />

      <Access />

      <Drives disks={st.disks ?? []} />

      <PanelSection title={t("steam")}>
        <PanelSectionRow>
          <Field label={t("playing")} bottomSeparator="none">
            {sm.running ? sm.running.name ?? `AppID ${sm.running.appid}` : t("nothing")}
          </Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field label={t("installed")} bottomSeparator="none">
            {sm.games?.length ?? 0} · {gb(sm.total_size)}
          </Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field label={t("wifi")} bottomSeparator="none">
            {n.wifi ? `${n.wifi.ssid} · ${n.wifi.signal}%` : t("disconnected")}
          </Field>
        </PanelSectionRow>
      </PanelSection>
    </>
  );
}

export default definePlugin(() => {
  initLanguage();
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
