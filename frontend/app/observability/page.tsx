"use client";

import { useEffect, useState } from "react";
import Shell, { Spinner, ErrorBox } from "@/components/Shell";
import { useLang } from "@/lib/lang";
import { api, type Observability } from "@/lib/api";

function successRate(a: { success: number; failed: number }) {
  const total = a.success + a.failed;
  return total === 0 ? 100 : Math.round((a.success / total) * 100);
}

export default function ObservabilityPage() {
  const { t } = useLang();
  const [obs, setObs] = useState<Observability | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.observability().then(setObs).catch((e) => setError(e instanceof Error ? e.message : "Could not load"));
  }, []);

  if (!obs && !error) return <Shell title={t("obs.title")} subtitle={t("obs.subtitle")}><Spinner /></Shell>;

  const c = obs?.counts ?? {};
  const tokens = obs?.tokens_total ?? 0;
  const agentMax = Math.max(1, ...(obs?.executions_by_agent.map(a => a.executions) ?? [1]));
  const domainMax = Math.max(1, ...(obs?.tasks_by_domain.map(d => d.total) ?? [1]));

  return (
    <Shell title={t("obs.title")} subtitle={t("obs.subtitle")}>
      {error && <ErrorBox error={error} />}

      {obs && (
        <>
          {/* KPI strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="card"><div className="muted text-xs">{t("obs.executions")}</div><div className="metric mt-1">{c.executions ?? 0}</div></div>
            <div className="card"><div className="muted text-xs">{t("obs.success_rate")}</div><div className="metric mt-1 text-[color:var(--ok)]">{successRate({ success: obs.executions_by_agent.reduce((s, a) => s + a.success, 0), failed: obs.executions_by_agent.reduce((s, a) => s + a.failed, 0) })}%</div></div>
            <div className="card">
              <div className="muted text-xs">{t("obs.tokens")}</div>
              <div className="metric mt-1">{tokens.toLocaleString()}</div>
              <div className="mt-1 space-y-0.5">
                <div className="muted text-[10px]">{t("obs.executions_with_data")}: <b>{obs.executions_with_token_data ?? 0}</b> · {t("obs.tokens_source")}: <b dir="ltr">{obs.tokens_source ?? "unmeasured"}</b></div>
                <div className="muted text-[10px]">{t("obs.tokens_unmeasured")}: <b>{obs.executions_unmeasured ?? 0}</b></div>
                <div className="muted text-[10px]">{t("obs.budget_estimate")}: <b>${(obs.budget_estimate_usd ?? 0).toFixed(2)}</b></div>
              </div>
            </div>
            <div className="card"><div className="muted text-xs">{t("obs.needs_you")}</div><div className="metric mt-1 text-[color:var(--warn)]">{obs.approvals.pending}</div></div>
          </div>

          <div className="mt-6 grid lg:grid-cols-2 gap-6">
            {/* By domain */}
            <section className="card">
              <h2 className="font-bold">{t("obs.by_department")}</h2>
              <div className="mt-3 space-y-2">
                {obs.tasks_by_domain.map((d) => (
                  <div key={d.domain} className="flex items-center gap-3">
                    <div className="w-40 shrink-0 text-[12px] truncate" dir="ltr">{d.domain}</div>
                    <div className="h-6 flex-1 rounded bg-black/40 overflow-hidden">
                      <div className="h-full bg-gradient-to-l from-[color:var(--gold-deep)] to-[color:var(--gold)]" style={{ width: `${(d.total / domainMax) * 100}%` }} />
                    </div>
                    <div className="w-8 text-end text-[11px] muted">{d.total}</div>
                  </div>
                ))}
                {obs.tasks_by_domain.length === 0 && <p className="muted text-sm">{t("obs.no_data")}</p>}
              </div>
            </section>

            {/* By agent */}
            <section className="card">
              <h2 className="font-bold">{t("obs.by_agent")}</h2>
              <div className="mt-3 space-y-2">
                {obs.executions_by_agent.map((a) => (
                  <div key={a.agent} className="flex items-center gap-3">
                    <div className="w-40 shrink-0 text-[12px] truncate" dir="ltr" title={a.token_source === "measured" ? "tokens measured from provider" : "tokens unmeasured (provider returned none)"}>
                      {a.agent}
                      <span className={`ms-1 text-[9px] ${a.token_source === "measured" ? "text-[color:var(--ok)]" : "muted"}`}>({a.token_source ?? "unmeasured"})</span>
                    </div>
                    <div className="h-6 flex-1 rounded bg-black/40 overflow-hidden">
                      <div className="h-full bg-gradient-to-l from-[color:var(--teal)]/60 to-[color:var(--teal)]" style={{ width: `${(a.executions / agentMax) * 100}%` }} />
                    </div>
                    <div className="w-8 text-end text-[11px] muted">{a.executions}</div>
                  </div>
                ))}
                {obs.executions_by_agent.length === 0 && <p className="muted text-sm">{t("obs.no_data")}</p>}
              </div>
            </section>
          </div>

          <div className="mt-6 grid lg:grid-cols-3 gap-6">
            {/* Approvals breakdown */}
            <section className="card">
              <h2 className="font-bold">{t("obs.approvals_breakdown")}</h2>
              <ul className="mt-3 space-y-2 text-sm">
                <li className="flex justify-between"><span className="badge badge-warn">pending</span><b>{obs.approvals.pending}</b></li>
                <li className="flex justify-between"><span className="badge badge-ok">approved</span><b>{obs.approvals.approved}</b></li>
                <li className="flex justify-between"><span className="badge badge-err">rejected</span><b>{obs.approvals.rejected}</b></li>
              </ul>
              <div className="hairline" />
              <div className="muted text-[11px]">LLM: {obs.llm_mode}<br />DB: {obs.db_backend}{obs.db_diag ? ` — ${obs.db_diag}` : ""}</div>
            </section>

            {/* Recent tasks */}
            <section className="card lg:col-span-2">
              <h2 className="font-bold">{t("obs.recent_tasks")}</h2>
              <ul className="mt-3 divide-y divide-[color:var(--line)] text-sm">
                {obs.recent_tasks.slice(0, 8).map((tk) => (
                  <li key={String(tk.task_id)} className="flex items-center justify-between gap-3 py-2">
                    <span className="min-w-0"><span className="badge badge-teal !text-[10px] me-2">#{String(tk.task_id)}</span>{String(tk.type)} → <b>{String(tk.domain)}</b></span>
                    <span className={`badge ${tk.status === "success" ? "badge-ok" : tk.status === "failed" ? "badge-err" : "badge-warn"} shrink-0`}>{String(tk.status)}</span>
                  </li>
                ))}
                {obs.recent_tasks.length === 0 && <li className="muted py-3">{t("obs.no_data")}</li>}
              </ul>
            </section>
          </div>

          {/* Audit feed */}
          <section className="card mt-6">
            <h2 className="font-bold">{t("obs.audit_feed")}</h2>
            <ul className="mt-3 divide-y divide-[color:var(--line)] text-[12px]">
              {obs.audit.slice(0, 15).map((a) => (
                <li key={a.log_id} className="flex items-start gap-3 py-1.5">
                  <span className="badge badge-gold !text-[10px] shrink-0">{a.actor}</span>
                  <span className="min-w-0"><b>{a.action}</b> — <span className="muted">{(a.detail ?? "").slice(0, 120)}</span></span>
                </li>
              ))}
              {obs.audit.length === 0 && <li className="muted py-3">{t("obs.no_data")}</li>}
            </ul>
          </section>
        </>
      )}
    </Shell>
  );
}
