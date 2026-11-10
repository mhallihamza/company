"use client";

import { useEffect, useState } from "react";
import Shell, { Spinner, ErrorBox } from "@/components/Shell";
import { useLang } from "@/lib/lang";
import { api, type Settings, type AuditEntry } from "@/lib/api";

export default function SettingsPage() {
  const { t } = useLang();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api.settings().then(setSettings).catch((e) => setError(e instanceof Error ? e.message : "Could not load"));
    api.audit(8).then(setAudit).catch(() => setAudit([]));
  }, []);

  async function setAutonomy(level: number) {
    setMsg("");
    try {
      const out = await api.setAutonomy(level);
      setSettings((s) => s ? { ...s, autonomy_level: out.autonomy_level } : s);
      setMsg(`✅ Autonomy set to level ${level}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    }
  }

  function clearToken() {
    localStorage.removeItem("founder_token");
    setMsg("🧹 Founder token cleared from this browser — you’ll be asked on the next request.");
  }

  return (
    <Shell title={t("settings.title")} subtitle={t("settings.subtitle")}>
      {error && <ErrorBox error={error} />}
      {!settings && !error && <Spinner />}
      {msg && <div className="mb-4 rounded-xl border border-[color:var(--gold)]/40 bg-[color:var(--gold)]/10 px-4 py-3 text-sm">{msg}</div>}

      {settings && (
        <div className="grid lg:grid-cols-2 gap-6">
          {/* Autonomy */}
          <section className="card">
            <h2 className="text-lg font-bold">🎚️ {t("settings.autonomy")}</h2>
            <div className="mt-4 space-y-3">
              {settings.autonomy_levels.map((l) => (
                <button key={l.level}
                  onClick={() => setAutonomy(l.level)}
                  className={`w-full rounded-2xl border p-4 text-start transition-all ${
                    settings.autonomy_level === l.level
                      ? "border-[color:var(--gold)] bg-[color:var(--gold)]/10"
                      : "border-[color:var(--line)] hover:bg-white/5"}`}>
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl text-lg font-extrabold ${
                        settings.autonomy_level === l.level ? "bg-[color:var(--gold)] text-[#241b08]" : "bg-white/10"}`}>
                        {l.level}
                      </div>
                      <div className="min-w-0">
                        <div className="font-bold">{l.name}</div>
                        <div className="muted text-[11px]">{l.describe}</div>
                      </div>
                    </div>
                    {settings.autonomy_level === l.level && <span className="badge badge-gold shrink-0">active</span>}
                  </div>
                </button>
              ))}
            </div>
          </section>

          {/* Keys + Etsy status */}
          <section className="card">
            <h2 className="text-lg font-bold">🔑 {t("settings.keys")}</h2>
            <div className="mt-4 divide-y divide-[color:var(--line)]">
              {Object.entries(settings.keys).map(([k, v]) => (
                <div key={k} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                  <span className="font-mono text-[12px] text-[color:var(--muted)]" dir="ltr">{k}</span>
                  <span className="font-mono" dir="ltr">{v}</span>
                </div>
              ))}
            </div>
            <div className="mt-4 rounded-xl border border-[color:var(--line)] p-3">
              <div className="font-bold">Etsy Open API v3</div>
              <div className="muted text-[11px] mt-0.5">
                {settings.etsy.status === "configured"
                  ? "🟢 Configured — real listing uploads allowed after your sign-off"
                  : "⚪ Not configured — publishing stays in draft_mock until env vars are set"}
              </div>
              <div className="grid grid-cols-2 gap-1.5 mt-3 text-[11px]">
                {Object.entries(settings.etsy.variables)
                  .filter(([k]) => k !== "etsy_configured" && k !== "etsy_taxonomy_id")
                  .map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between gap-2">
                      <span className="muted font-mono">{k}</span>
                      <span className={`badge ${v ? "badge-ok" : "badge-err"} !text-[10px]`}>{v ? "set" : "missing"}</span>
                    </div>
                  ))}
              </div>
            </div>
            <div className="mt-4 flex items-center justify-between gap-3 rounded-xl border border-[color:var(--line)] p-3">
              <div className="text-sm">
                <div className="font-bold">{t("settings.model")}</div>
                <div className="muted text-xs">{settings.llm_mode}</div>
              </div>
              <div className="text-sm text-end">
                <div className="font-bold">{t("settings.db")}</div>
                <div className="muted text-xs">{settings.db_backend}</div>
              </div>
            </div>
            <div className="mt-3 flex items-center justify-between gap-3 text-sm">
              <span>{t("settings.scheduler")}</span>
              <span className={`badge ${settings.scheduler_enabled ? "badge-ok" : "badge"}`}>
                {settings.scheduler_enabled ? t("settings.scheduler_on") : t("settings.scheduler_off")}
              </span>
            </div>

            <button className="btn btn-ghost btn-sm mt-4" onClick={clearToken}>{t("settings.clear_token")}</button>
          </section>
        </div>
      )}

      {/* Audit log */}
      <section className="card mt-6">
        <h2 className="text-lg font-bold">{t("settings.audit")}</h2>
        <ul className="mt-3 divide-y divide-[color:var(--line)]">
          {audit.map((a) => (
            <li key={a.log_id} className="flex items-start justify-between gap-4 py-2 text-sm">
              <span className="min-w-0"><span className="badge badge-teal !text-[10px] me-2">{a.actor}</span><b>{a.action}</b> · <span className="muted">{(a.detail ?? "").slice(0, 110)}</span></span>
              <span className="muted text-[11px] shrink-0">{a.created_at}</span>
            </li>
          ))}
          {audit.length === 0 && <li className="muted py-3">No runs recorded yet.</li>}
        </ul>
      </section>
    </Shell>
  );
}
