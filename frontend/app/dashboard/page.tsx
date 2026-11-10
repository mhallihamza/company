"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Shell, { Spinner, ErrorBox } from "@/components/Shell";
import { useLang } from "@/lib/lang";
import { api, type AdminHealth, type Approval, type AuditEntry, type Observability, type Settings } from "@/lib/api";

function successRate(obs: Observability | null): string {
  if (!obs) return "—";
  let ok = 0, bad = 0;
  for (const d of obs.tasks_by_domain ?? []) {
    ok += Number(d.success ?? 0);
    bad += Number(d.failed ?? 0);
  }
  const total = ok + bad;
  return total === 0 ? "—" : `${Math.round((ok / total) * 100)}%`;
}

function Kpi({ label, value, hint, accent }: { label: string; value: React.ReactNode; hint?: string; accent?: "gold" | "teal" | "warn" }) {
  const color = accent === "gold" ? "text-[color:var(--gold)]"
    : accent === "teal" ? "text-[color:var(--teal)]"
    : accent === "warn" ? "text-[color:var(--warn)]" : "";
  return (
    <div className="card kpi-tile">
      <div className="eyebrow">{label}</div>
      <div className={`metric ${color}`}>{value}</div>
      {hint && <div className="muted text-[10.5px]">{hint}</div>}
    </div>
  );
}

export default function Dashboard() {
  const { t } = useLang();
  const [health, setHealth] = useState<AdminHealth | null>(null);
  const [obs, setObs] = useState<Observability | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyApproval, setBusyApproval] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const [h, o, s, a, au] = await Promise.all([
        api.adminHealth(),
        api.observability().catch(() => null),
        api.settings().catch(() => null),
        api.approvals("pending").catch(() => [] as Approval[]),
        api.audit(8).catch(() => [] as AuditEntry[]),
      ]);
      setHealth(h); setObs(o); setSettings(s); setApprovals(a); setAudit(au);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach the server");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const decide = useCallback(async (id: number, decision: "approve" | "reject") => {
    setBusyApproval(id);
    try {
      await api.decideApproval(id, decision, "dashboard one-click");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Decision failed");
    } finally {
      setBusyApproval(null);
    }
  }, [load]);

  if (loading) return <Shell title={t("nav.dashboard")}><Spinner /></Shell>;

  const c = health?.counts ?? {};
  const etsyReady = !!health?.etsy?.etsy_configured;
  const autonomy = settings?.autonomy_level ?? 1;
  const autonomyName = settings?.autonomy_levels?.find((l) => l.level === autonomy)?.name ?? `L${autonomy}`;

  return (
    <Shell title={t("dash.title")} subtitle={t("dash.subtitle")}>
      {error && <ErrorBox error={error} />}

      {/* ===== Hero — command center ===== */}
      <section className="hero-border fade-in">
        <div className="card p-6 sm:p-7">
          <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr] lg:items-center">
            <div className="min-w-0">
              <div className="eyebrow flex items-center gap-2">
                <span className="status-dot" />{t("dash.command_eyebrow")}
              </div>
              <h2 className="mt-3 text-3xl sm:text-[2.6rem] font-black tracking-[-0.04em] leading-[1.06]">{t("dash.headline")}</h2>
              <p className="muted mt-3 max-w-lg text-[13.5px] leading-relaxed">{t("dash.sub")}</p>
              <div className="mt-5 flex flex-wrap items-center gap-2">
                <Link href="/ceo" className="btn btn-gold">{t("dash.ceo_cta")}</Link>
                <Link href="/approvals" className="btn btn-ghost">{t("dash.review_approvals")}{(c.approvals_pending ?? 0) > 0 ? ` · ${c.approvals_pending}` : ""}</Link>
              </div>
            </div>

            {/* System pulse panel */}
            <div className="rounded-2xl border border-[color:var(--line)] bg-black/30 p-4 sm:p-5">
              <div className="eyebrow">{t("dash.system_pulse")}</div>
              <div className="mt-1">
                <div className="pulse-row">
                  <span className="muted">{t("dash.db_row")}</span>
                  <span className="mono text-[11px] truncate text-end">{health?.db_backend ?? "—"}</span>
                </div>
                <div className="pulse-row">
                  <span className="muted">{t("dash.llm_row")}</span>
                  <span className="flex items-center gap-2">
                    <span className="mono text-[11px] max-w-[130px] truncate text-end">{health?.llm_mode ?? "—"}</span>
                    {health?.llm_mode?.startsWith("demo")
                      ? <span className="badge badge-warn !text-[9.5px]">demo</span>
                      : <span className="badge badge-ok !text-[9.5px]">live</span>}
                  </span>
                </div>
                <div className="pulse-row">
                  <span className="muted">{t("dash.autonomy_row")}</span>
                  <span className="badge badge-gold">L{autonomy} · {autonomyName}</span>
                </div>
                <div className="pulse-row">
                  <span className="muted">{t("dash.etsy_row")}</span>
                  <span className="flex items-center gap-2">
                    <span className={`status-dot ${etsyReady ? "" : "!bg-[color:var(--warn)]"}`} style={etsyReady ? undefined : { background: "var(--warn)" }} />
                    <span className={etsyReady ? "text-[color:var(--ok)]" : "text-[color:var(--warn)]"}>
                      {etsyReady ? t("dash.etsy_ready") : t("dash.etsy_missing")}
                    </span>
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ===== KPI strip ===== */}
      <section className="mt-5 grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 fade-in delay-1">
        <Kpi label={t("dash.kpi_tasks")} value={c.tasks ?? 0} hint={t("dash.kpi_lifetime")} />
        <Kpi label={t("dash.kpi_executions")} value={c.executions ?? 0} hint={t("dash.kpi_lifetime")} />
        <Kpi label={t("dash.kpi_success")} value={successRate(obs)} accent="teal" hint={t("dash.kpi_success_hint")} />
        <Kpi label={t("dash.kpi_opportunities")} value={c.opportunities ?? 0} accent="gold" hint={t("dash.kpi_lifetime")} />
        <Kpi label={t("dash.kpi_published")} value={c.products_published ?? 0} accent="teal" hint={t("dash.kpi_lifetime")} />
        <Kpi label={t("dash.kpi_pending")} value={c.approvals_pending ?? 0} accent="warn" hint={t("dash.your_queue_hint")} />
      </section>

      {/* ===== Queue + Operations feed ===== */}
      <div className="mt-6 grid gap-5 lg:grid-cols-5">
        {/* Your queue */}
        <section className="card lg:col-span-2 fade-in delay-2 flex flex-col">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="eyebrow">{t("dash.your_queue")}</div>
              <h3 className="mt-1 text-lg font-bold tracking-tight">{t("dash.approvals")}</h3>
            </div>
            <Link href="/approvals" className="btn btn-ghost btn-sm">{t("nav.approvals")} →</Link>
          </div>
          <div className="mt-4 space-y-2 flex-1">
            {approvals.slice(0, 4).map((a) => (
              <div key={a.approval_id} className="rounded-xl border border-[color:var(--line)] p-3 bg-white/[0.02]">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-[13px] font-semibold">#{a.approval_id} <span className="muted font-normal">· {a.kind}</span></div>
                    <div className="muted text-[11px] truncate mt-0.5">{a.note || a.ref}</div>
                  </div>
                  <div className="flex shrink-0 gap-1.5">
                    <button className="btn btn-green btn-sm" disabled={busyApproval === a.approval_id} onClick={() => decide(a.approval_id, "approve")} aria-label="Approve">✓</button>
                    <button className="btn btn-red btn-sm" disabled={busyApproval === a.approval_id} onClick={() => decide(a.approval_id, "reject")} aria-label="Reject">✕</button>
                  </div>
                </div>
              </div>
            ))}
            {approvals.length === 0 && (
              <div className="rounded-xl border border-dashed border-[color:var(--line-strong)] p-6 text-center">
                <div className="text-2xl">✅</div>
                <div className="mt-2 text-sm font-semibold">{t("dash.approvals_empty")}</div>
                <p className="muted mt-1 text-[11.5px]">{t("dash.queue_all_clear")}</p>
              </div>
            )}
          </div>
        </section>

        {/* Operations feed */}
        <section className="card lg:col-span-3 fade-in delay-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="eyebrow">{t("dash.ops_feed")}</div>
              <h3 className="mt-1 text-lg font-bold tracking-tight">{t("dash.audit")}</h3>
            </div>
            <span className="badge badge-teal mono !text-[10px]">audit_logs</span>
          </div>
          <ul className="timeline mt-4">
            {audit.map((a) => (
              <li key={a.log_id}>
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
                  <span className="badge badge-teal !text-[9.5px] shrink-0">{a.actor}</span>
                  <b className="text-[12.5px]">{a.action}</b>
                  {a.created_at && <span className="muted mono text-[10px]">{new Date(a.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>}
                </div>
                {a.detail && <p className="muted text-[11.5px] mt-1 leading-snug">{a.detail.slice(0, 110)}{a.detail.length > 110 ? "…" : ""}</p>}
              </li>
            ))}
            {audit.length === 0 && <li className="muted text-sm border-l-0 pl-0">No activity yet — run something from the CEO Chat.</li>}
          </ul>
        </section>
      </div>

      {/* ===== Quick actions ===== */}
      <section className="mt-6 fade-in delay-3">
        <div className="eyebrow mb-2">{t("dash.quick_actions")}</div>
        <div className="flex flex-wrap gap-2">
          <Link href="/ceo" className="chip">🔍 {t("dash.action_market")}</Link>
          <Link href="/books" className="chip">✍️ {t("dash.action_story")}</Link>
          <Link href="/opportunities" className="chip">💰 {t("dash.action_opps")}</Link>
          <Link href="/profiles" className="chip">🌍 {t("dash.action_markets")}</Link>
          <Link href="/reports" className="chip">📄 {t("dash.action_reports")}</Link>
          <Link href="/observability" className="chip">📡 {t("dash.action_obs")}</Link>
        </div>
      </section>

      <p className="mono mt-6 text-[10px] text-[#4b5568]">AI BUSINESS HQ · v{health?.version ?? "3.2.0"} · human-in-the-loop · every external action waits for your approval</p>
    </Shell>
  );
}
