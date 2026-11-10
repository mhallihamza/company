"use client";

import { useEffect, useState } from "react";
import Shell, { Spinner, ErrorBox } from "@/components/Shell";
import { useLang } from "@/lib/lang";
import { api, type AdminHealth, type Approval, type AuditEntry } from "@/lib/api";

function Kpi({ label, value, hint, tone = "" }: { label: string; value: React.ReactNode; hint?: string; tone?: string }) {
  return (
    <div className="card">
      <div className="muted text-xs">{label}</div>
      <div className={`metric mt-2 ${tone}`}>{value}</div>
      {hint && <div className="muted mt-1 text-[11px]">{hint}</div>}
    </div>
  );
}

export default function Dashboard() {
  const { t } = useLang();
  const [health, setHealth] = useState<AdminHealth | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [h, a, au] = await Promise.all([
          api.adminHealth(),
          api.approvals("pending").catch(() => [] as Approval[]),
          api.audit(8).catch(() => [] as AuditEntry[]),
        ]);
        setHealth(h); setApprovals(a); setAudit(au);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not reach the server");
      } finally { setLoading(false); }
    })();
  }, []);

  if (loading) return <Shell title={t("nav.dashboard")}><Spinner /></Shell>;
  const c = health?.counts ?? {};

  return (
    <Shell title={t("dash.title")} subtitle={t("dash.subtitle")}>
      {error && <ErrorBox error={error} />}

      {/* CEO briefing card */}
      <section className="card mb-6 fade-in">
        <div className="flex items-start justify-between gap-6 flex-wrap">
          <div className="max-w-2xl">
            <div className="badge badge-gold mb-3">{t("dash.ceo_card_badge")}</div>
            <h2 className="text-2xl font-extrabold leading-snug">{t("dash.ceo_headline")}</h2>
            <p className="muted mt-2 text-sm">{t("dash.ceo_sub")}</p>
            <a href="/ceo" className="btn btn-gold mt-4">{t("dash.ceo_cta")}</a>
          </div>
          <div className="rounded-2xl border border-[color:var(--line)] p-4 text-center min-w-[180px]">
            <div className="muted text-xs">{t("dash.system_status")}</div>
            <div className="mt-2 text-lg font-bold text-[color:var(--ok)]">{t("dash.connected")}</div>
            <div className="muted mt-2 text-xs leading-6">
              <div>{t("dash.llm")}: <b>{health?.llm_mode}</b></div>
              <div>{t("dash.db")}: {health?.db_backend}</div>
            </div>
          </div>
        </div>
      </section>

      {/* KPIs */}
      <section className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
        <Kpi label={t("dash.kpi_tasks")} value={c.tasks ?? 0} />
        <Kpi label={t("dash.kpi_executions")} value={c.executions ?? 0} />
        <Kpi label={t("dash.kpi_opportunities")} value={c.opportunities ?? 0} tone="text-[color:var(--gold)]" />
        <Kpi label={t("dash.kpi_books")} value={c.products ?? 0} />
        <Kpi label={t("dash.kpi_published")} value={c.products_published ?? 0} tone="text-[color:var(--teal)]" />
        <Kpi label={t("dash.kpi_pending")} value={c.approvals_pending ?? 0} tone="text-[color:var(--warn)]" />
      </section>

      <div className="mt-6 grid lg:grid-cols-2 gap-6">
        {/* Pending approvals */}
        <section className="card">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold">{t("dash.approvals")}</h3>
            <a href="/approvals" className="btn btn-ghost btn-sm">{t("nav.approvals")} →</a>
          </div>
          <div className="mt-3 space-y-2">
            {approvals.slice(0, 4).map((a) => (
              <div key={a.approval_id} className="flex items-center justify-between gap-3 rounded-xl border border-[color:var(--line)] p-3">
                <div className="min-w-0">
                  <div className="font-semibold">#{a.approval_id} — {a.kind}</div>
                  <div className="muted text-xs truncate">{a.note}</div>
                </div>
                <span className="badge badge-warn shrink-0">{t("dash.kpi_pending")}</span>
              </div>
            ))}
            {approvals.length === 0 && <p className="muted py-3 text-sm">{t("dash.approvals_empty")}</p>}
          </div>
        </section>

        {/* Audit feed */}
        <section className="card">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold">{t("dash.audit")}</h3>
            <span className="muted text-xs">audit_logs</span>
          </div>
          <ul className="mt-3 space-y-2 text-sm">
            {audit.map((a) => (
              <li key={a.log_id} className="flex items-start gap-2 rounded-lg px-2 py-1.5 hover:bg-white/5">
                <span className="badge badge-teal shrink-0 !text-[10px]">{a.actor}</span>
                <span className="min-w-0"><b>{a.action}</b> — <span className="muted">{(a.detail ?? "").slice(0, 90)}</span></span>
              </li>
            ))}
            {audit.length === 0 && <li className="muted py-3">No activity yet</li>}
          </ul>
        </section>
      </div>
    </Shell>
  );
}
