"use client";

import { useEffect, useState } from "react";
import Shell, { Spinner, Empty } from "@/components/Shell";
import { useLang } from "@/lib/lang";
import { api, type Book, type Opportunity } from "@/lib/api";

export default function ProductsPage() {
  const { t } = useLang();
  const [books, setBooks] = useState<Book[] | null>(null);
  const [pursuing, setPursuing] = useState<Opportunity[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.books().catch(() => [] as Book[]),
      api.opportunities("", "pursuing").catch(() => [] as Opportunity[]),
    ]).then(([b, p]) => { setBooks(b); setPursuing(p); })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load"));
  }, []);

  return (
    <Shell title={t("products.title")} subtitle={t("products.subtitle")}>
      {error && <p className="text-sm text-[color:var(--err)]">{error}</p>}
      {!books && <Spinner />}

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Candidates */}
        <section className="card">
          <h2 className="text-lg font-bold">🆕 {t("products.pursuing")}</h2>
          <p className="muted mt-1 text-sm">{t("products.pursuing_sub")}</p>
          <div className="mt-4 space-y-2">
            {pursuing.map((o) => (
              <div key={o.opportunity_id} className="flex items-center justify-between gap-3 rounded-xl border border-[color:var(--line)] p-3">
                <div className="min-w-0">
                  <div className="font-semibold text-sm leading-6">{o.title}</div>
                  <div className="muted text-[11px]">#{o.opportunity_id} · {o.sector} · {(o.score ?? 0).toFixed(1)}/10</div>
                </div>
                <span className="badge badge-gold shrink-0">pursuing</span>
              </div>
            ))}
            {pursuing.length === 0 && <Empty icon="📦" title={t("products.empty_candidates")} />}
          </div>
        </section>

        {/* Pipeline */}
        <section className="card">
          <h2 className="text-lg font-bold">🏭 {t("products.pipeline")}</h2>
          <p className="muted mt-1 text-sm">{t("products.pipeline_sub")}</p>
          <div className="mt-4 space-y-2">
            {books?.map((b) => (
              <div key={b.slug} className="flex items-center justify-between gap-3 rounded-xl border border-[color:var(--line)] p-3">
                <div className="min-w-0">
                  <div className="font-semibold text-sm leading-6">{b.title}</div>
                  <div className="muted text-[11px] font-mono" dir="ltr">{b.slug}</div>
                </div>
                <span className="badge badge-teal shrink-0">{b.status}</span>
              </div>
            ))}
            {books && books.length === 0 && <Empty icon="📚" title={t("products.empty_pipeline")} />}
          </div>
        </section>
      </div>
    </Shell>
  );
}
