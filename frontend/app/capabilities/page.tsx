"use client";

import { useEffect, useState } from "react";
import Shell, { Spinner, ErrorBox, Empty } from "@/components/Shell";
import { useLang } from "@/lib/lang";
import { api, type Capability } from "@/lib/api";

export default function CapabilitiesPage() {
  const { t } = useLang();
  const [caps, setCaps] = useState<Capability[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.capabilities().then(setCaps).catch((e) => setError(e instanceof Error ? e.message : "Could not load"));
  }, []);

  return (
    <Shell title={t("caps.title")} subtitle={t("caps.subtitle")}>
      {error && <ErrorBox error={error} />}
      {!caps && !error && <Spinner />}
      {caps && caps.length === 0 && <Empty title="No capabilities registered" />}

      <div className="grid md:grid-cols-2 gap-4">
        {caps?.map((c) => (
          <div key={c.id} className="card">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h2 className="font-bold">🧩 {c.title_en}</h2>
                <div className="muted text-[11px] font-mono mt-0.5" dir="ltr">{c.id}</div>
              </div>
              <div className="flex flex-col items-end gap-1.5 shrink-0">
                <span className={`badge ${c.deterministic ? "badge-teal" : "badge-gold"}`}>{c.deterministic ? t("caps.deterministic") : t("caps.llm")}</span>
                <span className="muted text-[10px]">v{c.version}</span>
              </div>
            </div>
            <p className="muted mt-3 text-sm leading-6">{c.description_en}</p>
            <div className="hairline" />
            <div className="flex items-center justify-between gap-3">
              <span className="text-[11px] muted">{t("caps.used_by")}:</span>
              <div className="flex flex-wrap gap-1">
                {c.used_by.map((d) => <span key={d} className="badge badge-gold !text-[10px]">{d}</span>)}
              </div>
            </div>
          </div>
        ))}
      </div>
    </Shell>
  );
}
