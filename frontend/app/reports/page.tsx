"use client";

import { useEffect, useState } from "react";
import Shell, { Spinner, ErrorBox, Empty } from "@/components/Shell";
import SourceBadge from "@/components/SourceBadge";
import { useLang } from "@/lib/lang";
import { api, type Report } from "@/lib/api";

export default function ReportsPage() {
  const { t } = useLang();
  const [reports, setReports] = useState<Report[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<Report | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  useEffect(() => {
    api.reports(60).then(setReports).catch((e) => setError(e instanceof Error ? e.message : "Could not load"));
  }, []);

  async function download(r: Report) {
    setBusy(r.report_id);
    try {
      const name = (r.path ?? "report.pdf").split(/[\\/]/).pop() ?? `report-${r.report_id}`;
      await api.downloadReport(r.report_id, name);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Download failed");
    } finally { setBusy(null); }
  }

  return (
    <Shell title={t("reports.title")} subtitle={t("reports.subtitle")}>
      {error && <ErrorBox error={error} />}
      {!reports && !error && <Spinner />}
      {reports && reports.length === 0 && (
        <Empty icon="📄" title={t("reports.empty")} hint={t("reports.empty_hint")} />
      )}

      <div className="grid lg:grid-cols-3 gap-5">
        <div className="lg:col-span-1 space-y-2">
          {reports?.map((r) => (
            <button key={r.report_id}
              onClick={() => setOpen(r)}
              className={`w-full text-start rounded-xl border p-4 transition-all ${
                open?.report_id === r.report_id
                  ? "border-[color:var(--gold)] bg-[color:var(--gold)]/10"
                  : "border-[color:var(--line)] bg-[color:var(--card)] hover:bg-white/5"}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-bold text-sm leading-6 text-start flex-1 min-w-0 truncate">{r.title ?? "Report"}</span>
                <span className="flex items-center gap-1.5 shrink-0">
                  <SourceBadge source={r.source} />
                  <span className="badge badge-teal !text-[10px]">{r.kind}</span>
                </span>
              </div>
              <div className="muted text-[11px] mt-1 flex items-center justify-between gap-2">
                <span className="truncate" dir="ltr">{(r.path ?? "").split(/[\\/]/).pop()}</span>
                <span className="shrink-0">{r.created_at?.slice(0, 10)}</span>
              </div>
            </button>
          ))}
        </div>

        {/* Viewer */}
        <div className="lg:col-span-2 card min-h-[50vh]">
          {!open && <div className="muted flex h-full items-center justify-center text-sm">{t("reports.select")}</div>}
          {open && (
            <>
              <div className="flex items-center justify-between gap-3 border-b border-[color:var(--line)] pb-3">
                <h2 className="font-bold text-lg">{open.title}</h2>
                <button className="btn btn-gold btn-sm" onClick={() => download(open)} disabled={busy === open.report_id}>
                  {busy === open.report_id ? "…" : `⬇ ${t("common.download")}`}
                </button>
              </div>
              <article className="mt-4 max-w-none text-sm leading-8 whitespace-pre-wrap">
                {open.content ?? t("reports.none")}
              </article>
            </>
          )}
        </div>
      </div>
    </Shell>
  );
}
