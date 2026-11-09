"use client";

import { useEffect, useState } from "react";
import Shell, { Spinner, ErrorBox, Empty } from "@/components/Shell";
import { useLang, type DictKey } from "@/lib/lang";
import { api, type AgentCard } from "@/lib/api";

const TIER: Record<string, [DictKey, string]> = {
  reasoning: ["agents.tier_reasoning", "badge-gold"],
  fast: ["agents.tier_fast", "badge-teal"],
  deterministic: ["agents.tier_deterministic", "badge"],
};

export default function AgentsPage() {
  const { t } = useLang();
  const [agents, setAgents] = useState<AgentCard[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.agents().then(setAgents).catch((e) => setError(e instanceof Error ? e.message : "Could not load"));
  }, []);

  // group by department
  const groups = agents
    ? Object.values(agents.reduce<Record<string, AgentCard[]>>((acc, a) => {
        (acc[a.department_key] ??= []).push(a); return acc;
      }, {}))
    : [];

  return (
    <Shell title={t("agents.title")} subtitle={t("agents.subtitle")}>
      {error && <ErrorBox error={error} />}
      {!agents && !error && <Spinner />}
      {agents && agents.length === 0 && <Empty title="No agents registered" />}

      <div className="space-y-6">
        {groups.map((roster) => (
          <section key={roster[0].department_key} className="card">
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div className="min-w-0">
                <h2 className="font-bold leading-6">{roster[0].department_title_en}</h2>
                <div className="muted text-[11px] font-mono" dir="ltr">{roster[0].department_key}</div>
              </div>
              <div className="flex flex-wrap gap-1.5">
                <span className="badge badge-teal">{roster.length} agents</span>
                <span className="badge">approval: {roster[0].approval_policy}</span>
              </div>
            </div>
            <div className="hairline" />
            <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-3">
              {roster.map((a) => {
                const [tierKey, tierCls] = TIER[a.tier] ?? ["agents.tier_deterministic", "badge"];
                return (
                  <div key={a.agent} className="rounded-xl border border-[color:var(--line)] p-3 hover:border-[color:var(--gold)]/40 transition-colors">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-bold text-sm">🤵 {a.agent}</span>
                      <span className={`badge ${tierCls} !text-[10px]`}>{t(tierKey)}</span>
                    </div>
                    <p className="muted text-[12px] mt-2 leading-5 min-h-[2.5rem]">{a.role}</p>
                    <div className="mt-2 flex items-center justify-between gap-2 text-[10px] text-[color:var(--muted)]">
                      <span dir="ltr">v{a.version}</span>
                      <span className="truncate" dir="ltr">{a.tools.join(", ")}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </Shell>
  );
}
