"use client";

import { useCallback, useEffect, useState } from "react";
import Shell, { Spinner, ErrorBox, Empty } from "@/components/Shell";
import { useLang } from "@/lib/lang";
import { api, type MarketProfile } from "@/lib/api";

type SeasonalEvent = { name: string; start?: string | null; end?: string | null; lead_weeks?: number };

function parseJson<T>(raw: string | undefined | null, fallback: T): T {
  if (!raw) return fallback;
  try {
    return (JSON.parse(raw) as T) ?? fallback;
  } catch {
    return fallback;
  }
}

export default function ProfilesPage() {
  const { t } = useLang();
  const [profiles, setProfiles] = useState<MarketProfile[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(
    () => api.profiles().then(setProfiles).catch((e) => setError(e instanceof Error ? e.message : "Could not load")),
    []
  );

  useEffect(() => { load(); }, [load]);

  async function toggle(id: number) {
    setBusy(id);
    setError(null);
    try {
      await api.toggleProfile(id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Toggle failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Shell title={t("profiles.title")} subtitle={t("profiles.subtitle")}>
      {error && <ErrorBox error={error} />}

      {!profiles && !error && <Spinner />}
      {profiles && profiles.length === 0 && <Empty title={t("profiles.empty")} />}

      <div className="grid gap-4 lg:grid-cols-3">
        {(profiles ?? []).map((p) => {
          const label = `${p.country}-${p.language}`.toUpperCase();
          const seeds = parseJson<string[]>(p.seeds, []);
          const calendar = parseJson<SeasonalEvent[]>(p.seasonal_calendar, []);
          const isRtl = (p.text_direction ?? p.dir) === "rtl";
          const verified = !!p.fee_verified;
          return (
            <section key={p.profile_id} className={`card ${p.enabled ? "" : "opacity-60"}`}>
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="badge badge-gold text-[11px]" dir="ltr">{label}</span>
                  <span className={`badge ${p.enabled ? "badge-ok" : "badge-warn"} text-[10px]`}>
                    {p.enabled ? t("profiles.enabled") : t("profiles.disabled")}
                  </span>
                </div>
                <button className="btn btn-ghost !w-auto text-[11px]" disabled={busy === p.profile_id} onClick={() => toggle(p.profile_id)}>
                  {t("profiles.toggle")}
                </button>
              </div>

              <div className="mt-4 space-y-2 text-[12px]">
                <div className="flex items-center justify-between gap-2">
                  <span className="muted">{t("profiles.fee_model")}</span>
                  <span className="flex items-center gap-2" dir="ltr">
                    <span dir="ltr">{p.fee_model_ref ?? "—"}</span>
                    <span className={`badge ${verified ? "badge-ok" : "badge-warn"}`}>
                      {verified ? t("profiles.verified") : t("profiles.partial")}
                    </span>
                  </span>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span className="muted">{t("profiles.prompt")}</span>
                  <span dir="ltr">{p.story_prompt_ref ?? "—"}</span>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span className="muted">{t("profiles.font")}</span>
                  <span dir="ltr">{p.font_ref ?? p.font ?? "—"}</span>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span className="muted">{t("profiles.direction")}</span>
                  <span dir="ltr" className="badge badge-teal">{isRtl ? "RTL" : "LTR"}</span>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span className="muted">{t("profiles.qa")}</span>
                  <span dir="ltr">{p.qa_ruleset_ref ?? "—"}</span>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span className="muted">Currency</span>
                  <span dir="ltr">{p.currency}</span>
                </div>
              </div>

              {seeds.length > 0 && (
                <div className="mt-3">
                  <div className="muted text-[10px] uppercase tracking-wide">{t("profiles.seeds")}</div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {seeds.map((s, i) => (
                      <span key={i} className="badge">{s}</span>
                    ))}
                  </div>
                </div>
              )}

              {calendar.length > 0 && (
                <div className="mt-3">
                  <div className="muted text-[10px] uppercase tracking-wide">{t("profiles.seasonal")}</div>
                  <ul className="mt-1 space-y-1 text-[11px]">
                    {calendar.map((ev, i) => (
                      <li key={i} className="flex items-center justify-between gap-2 border-b border-[color:var(--line)] pb-1">
                        <span className="truncate">{ev.name}</span>
                        <span className="muted shrink-0" dir="ltr">
                          {ev.start ?? "—"} → {ev.end ?? "—"}{ev.lead_weeks ? ` · ${t("profiles.lead_weeks")} ${ev.lead_weeks}w` : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </section>
          );
        })}
      </div>

      <p className="muted mt-6 text-[11px]">{t("profiles.note")}</p>
    </Shell>
  );
}
