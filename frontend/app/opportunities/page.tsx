"use client";

import { useCallback, useEffect, useState } from "react";
import Shell, { Spinner, ErrorBox, Empty } from "@/components/Shell";
import { useLang } from "@/lib/lang";
import { api, type Opportunity } from "@/lib/api";

const STATUS: Record<string, [string, string]> = {
  new: ["🆕 New", "badge-teal"],
  watching: ["👀 Watching", "badge"],
  pursuing: ["🎯 Pursuing", "badge-gold"],
  archived: ["🗄️ Archived", "badge-err"],
};

function statusBadge(s: string): [string, string] {
  return STATUS[s] ?? [s, "badge"];
}

export default function OpportunitiesPage() {
  const { t } = useLang();
  const [opps, setOpps] = useState<Opportunity[] | null>(null);
  const [sector, setSector] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback((sec = sector, st = status) =>
    api.opportunities(sec, st).then(setOpps).catch((e) => setError(e instanceof Error ? e.message : "Could not load")),
    [sector, status]);

  useEffect(() => { load(); }, [load]);

  async function setOppStatus(id: number, next: string) {
    setBusy(id); setError(null);
    try {
      await api.setOpportunityStatus(id, next);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    } finally { setBusy(null); }
  }

  return (
    <Shell title={t("opps.title")} subtitle={t("opps.subtitle")}
      actions={
        <>
          <select className="input !w-auto" value={sector} onChange={(e) => setSector(e.target.value)}>
            <option value="">{t("opps.sector_all")}</option>
            <option value="intelligence">intelligence</option>
            <option value="affiliate">affiliate</option>
            <option value="books">books</option>
          </select>
          <select className="input !w-auto" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">{t("opps.status_all")}</option>
            <option value="new">new</option>
            <option value="watching">watching</option>
            <option value="pursuing">pursuing</option>
            <option value="archived">archived</option>
          </select>
        </>
      }>
      {error && <ErrorBox error={error} />}
      {!opps && !error && <Spinner />}
      {opps && opps.length === 0 && (
        <Empty icon="💰" title={t("opps.empty")} hint={t("opps.empty_hint")} />
      )}

      <div className="grid md:grid-cols-2 gap-4">
        {opps?.map((o) => {
          const [label, cls] = statusBadge(o.status);
          const score = o.score ?? 0;
          return (
            <div key={o.opportunity_id} className="card">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="badge badge-gold !text-[10px]">{o.sector}</span>
                    <span className="muted text-[11px]">#{o.opportunity_id}</span>
                  </div>
                  <h3 className="mt-1.5 font-bold leading-6">{o.title}</h3>
                  <div className="muted mt-1 text-[11px]">{o.niche ?? "—"}</div>
                </div>
                <div className="text-center shrink-0">
                  <div className="metric !text-3xl text-[color:var(--gold)]">{score.toFixed(1)}</div>
                  <div className="muted text-[10px]">/10</div>
                </div>
              </div>

              <div className="mt-3 h-2 w-full rounded-full bg-black/40 overflow-hidden">
                <div className="h-full bg-gradient-to-l from-[color:var(--gold-deep)] to-[color:var(--gold)] transition-all" style={{ width: `${Math.min(100, score * 10)}%` }} />
              </div>

              <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-[color:var(--line)] pt-3">
                <span className={`badge ${cls}`}>{label}</span>
                <div className="flex gap-1.5">
                  <button className="btn btn-ghost btn-sm" disabled={busy === o.opportunity_id} onClick={() => setOppStatus(o.opportunity_id, "pursuing")}>{t("opps.pursuing")}</button>
                  <button className="btn btn-ghost btn-sm" disabled={busy === o.opportunity_id} onClick={() => setOppStatus(o.opportunity_id, "watching")}>{t("opps.watching")}</button>
                  <button className="btn btn-ghost btn-sm" disabled={busy === o.opportunity_id} onClick={() => setOppStatus(o.opportunity_id, "archived")}>{t("opps.archived")}</button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Shell>
  );
}
