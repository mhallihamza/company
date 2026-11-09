"use client";

import { useEffect, useState } from "react";
import Shell, { Spinner, ErrorBox, Empty } from "@/components/Shell";
import { useLang, type DictKey } from "@/lib/lang";
import { api, type Department } from "@/lib/api";

const SECTOR_ICON: Record<string, string> = {
  books: "📚", intelligence: "🧠", affiliate: "🧲", marketing: "📣",
  finance: "💵", qa: "🛡", design: "🎨", product: "📦",
};

const POLICY_BADGE: Record<string, [DictKey, string]> = {
  none: ["policy.none", "badge-teal"],
  story_review: ["policy.story_review", "badge-gold"],
  content_gate: ["policy.content_gate", "badge-warn"],
  human_required: ["policy.human_required", "badge-err"],
  gate: ["policy.gate", "badge-gold"],
};

export default function DepartmentsPage() {
  const { t } = useLang();
  const [depts, setDepts] = useState<Department[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, string>>({});
  const [tasks, setTasks] = useState<Record<string, string>>({});

  useEffect(() => {
    api.departments().then(setDepts).catch((e) => setError(e instanceof Error ? e.message : "Could not load"));
  }, []);

  async function runDept(key: string) {
    const task = (tasks[key] ?? "").trim();
    setRunning(key);
    setResult((r) => ({ ...r, [key]: "" }));
    try {
      const out = await api.runDepartment(key, task || "");
      setResult((r) => ({ ...r, [key]: out.summary ?? out.error ?? JSON.stringify(out).slice(0, 300) }));
    } catch (e) {
      setResult((r) => ({ ...r, [key]: e instanceof Error ? e.message : "Failed" }));
    } finally { setRunning(null); }
  }

  return (
    <Shell title={t("dept.title")} subtitle={t("dept.subtitle")}>
      {error && <ErrorBox error={error} />}
      {!depts && !error && <Spinner />}
      {depts && depts.length === 0 && <Empty title="No departments registered" />}

      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-5">
        {depts?.map((d) => {
          const [policyKey, policyCls] = POLICY_BADGE[d.approval_policy] ?? [d.approval_policy, "badge"];
          return (
            <div key={d.key} className="card flex flex-col">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-[11px] muted">{SECTOR_ICON[d.sector] ?? "🏭"} {d.sector}</div>
                  <h2 className="mt-1 text-lg font-bold leading-snug">{d.title_en}</h2>
                  <div className="text-[11px] muted" dir="ltr">{d.key}</div>
                </div>
                <span className={`badge ${policyCls}`}>{t(policyKey)}</span>
              </div>

              <p className="muted mt-3 text-sm leading-6 min-h-[3.5rem]">{d.description_en || d.description_ar}</p>

              <div className="mt-2 flex flex-wrap gap-1.5">
                {d.capabilities.slice(0, 4).map((c) => <span key={c} className="badge">{c}</span>)}
              </div>
              <div className="muted mt-2 text-[11px]">{t("dept.tools_allowed")}: {d.allowed_tools.join(", ")}</div>

              {/* Run */}
              <div className="mt-4 pt-4 border-t border-[color:var(--line)]">
                <input
                  className="input !py-2 text-sm"
                  placeholder={t("dept.placeholder")}
                  value={tasks[d.key] ?? ""}
                  onChange={(e) => setTasks((tk) => ({ ...tk, [d.key]: e.target.value }))}
                  onKeyDown={(e) => e.key === "Enter" && runDept(d.key)}
                />
                <button
                  className="btn btn-gold btn-sm mt-2 w-full justify-center"
                  onClick={() => runDept(d.key)}
                  disabled={running === d.key}
                >
                  {running === d.key ? t("dept.running") : t("dept.run")}
                </button>
                {result[d.key] && (
                  <div className="mt-2 rounded-lg border border-[color:var(--line)] bg-black/30 p-2 text-[12px] leading-6">
                    {result[d.key]}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Shell>
  );
}
