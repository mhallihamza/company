"use client";

import { useEffect, useState } from "react";
import Shell, { Spinner, ErrorBox, Empty } from "@/components/Shell";
import { useLang } from "@/lib/lang";
import { api, type Approval } from "@/lib/api";

export default function ApprovalsPage() {
  const { t } = useLang();
  const [pending, setPending] = useState<Approval[] | null>(null);
  const [history, setHistory] = useState<Approval[]>([]);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState<number | null>(null);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const [p, h] = await Promise.all([api.approvals("pending"), api.approvals("")]);
      setPending(p);
      setHistory(h.filter((a) => a.status !== "pending"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load");
    }
  };
  useEffect(() => { load(); }, []);

  async function decide(id: number, decision: "approve" | "reject") {
    setBusy(id); setMsg(""); setError(null);
    try {
      const out = await api.decideApproval(id, decision, notes[id] ?? "");
      if (decision === "approve" && out.listing_id) {
        setMsg(`✅ Approved — Etsy draft #${String(out.listing_id)} (${out.mock ? "MOCK" : "real"})`);
      } else {
        setMsg(decision === "approve" ? "✅ Approved" : "❌ Rejected");
      }
      setNotes((n) => ({ ...n, [id]: "" }));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Decision failed");
    } finally { setBusy(null); }
  }

  return (
    <Shell title={t("approvals.title")} subtitle={t("approvals.subtitle")}>
      {error && <ErrorBox error={error} />}
      {msg && <div className="mb-4 rounded-xl border border-[color:var(--gold)]/40 bg-[color:var(--gold)]/10 px-4 py-3 text-sm">{msg}</div>}

      <section>
        <h2 className="flex items-center gap-3 text-xl font-bold">
          {t("approvals.pending")} <span className="badge badge-warn">{pending?.length ?? "…"}</span>
        </h2>

        {!pending && !error && <Spinner />}
        {pending && pending.length === 0 && (
          <div className="mt-4"><Empty icon="✅" title={t("approvals.empty")} hint={t("approvals.empty_hint")} /></div>
        )}

        <div className="mt-4 grid md:grid-cols-2 gap-4">
          {pending?.map((a) => (
            <div key={a.approval_id} className="card border-l-4 border-[color:var(--warn)] fade-in">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="font-bold">#{a.approval_id} — {a.kind}</div>
                  <div className="muted text-xs mt-0.5 font-mono" dir="ltr">{a.ref}</div>
                </div>
                <span className="badge badge-warn shrink-0">pending</span>
              </div>
              <p className="muted mt-2 text-sm">{a.note || "No note"}</p>
              <p className="muted mt-1 text-[11px]">{a.created_at}</p>

              <textarea className="textarea mt-3 !min-h-[56px] text-sm" placeholder={t("approvals.note")}
                value={notes[a.approval_id] ?? ""}
                onChange={(e) => setNotes((n) => ({ ...n, [a.approval_id]: e.target.value }))} />
              <div className="mt-3 grid grid-cols-2 gap-2">
                <button className="btn btn-green justify-center" disabled={busy === a.approval_id} onClick={() => decide(a.approval_id, "approve")}>
                  {t("approvals.approve")}<span className="text-xs opacity-70">&nbsp;&amp;execute</span>
                </button>
                <button className="btn btn-red justify-center" disabled={busy === a.approval_id} onClick={() => decide(a.approval_id, "reject")}>
                  {t("approvals.reject")}
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-bold text-[color:var(--muted)]">📜 {t("approvals.history")}</h2>
        <div className="card mt-3">
          {history.length === 0 && <p className="muted text-sm">No previous decisions.</p>}
          <ul className="divide-y divide-[color:var(--line)]">
            {history.slice(0, 12).map((a) => (
              <li key={a.approval_id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <span><span className={`badge ${a.status === "approved" ? "badge-ok" : "badge-err"} me-2`}>{a.status === "approved" ? t("approvals.approved") : t("approvals.rejected")}</span>#{a.approval_id} — {a.kind} — <span className="muted">{a.note}</span></span>
                <span className="muted text-[11px] shrink-0">{a.decided_at ?? a.created_at}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </Shell>
  );
}
