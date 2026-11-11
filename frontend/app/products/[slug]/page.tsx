"use client";

import { useEffect, useState, useTransition } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import Shell, { Spinner, ErrorBox, Empty } from "@/components/Shell";
import { useLang } from "@/lib/lang";
import { api, type Book, type Approval } from "@/lib/api";

type Asset = { asset_id: number; page_number: number | null; asset_type: string; path: string; provider: string | null; style: string | null };
type QaReport = { qa_id: number; verdict: string; checks: { name: string; ok: boolean; detail: string }[]; created_at: string };
type Brief = { product_key: string; title: string; target_age: string | null; format: string | null; page_count: number | null; marketplace: string | null; status: string; content: Record<string, unknown> };

export default function ProductWorkspace() {
  const { t } = useLang();
  const params = useParams<{ slug: string }>();
  const slug = params?.slug ?? "";
  const [book, setBook] = useState<Book | null | undefined>(undefined);
  const [story, setStory] = useState<Record<string, unknown> | null>(null);
  const [brief, setBrief] = useState<Brief | null | undefined>(undefined);
  const [assets, setAssets] = useState<Asset[] | undefined>(undefined);
  const [qaReports, setQaReports] = useState<QaReport[] | undefined>(undefined);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const load = async () => {
    setError(null);
    const [b, a, qa, p] = await Promise.all([
      api.book(slug).catch(() => ({ product: null, story: null })),
      fetch(`${api.base}/api/books/${encodeURIComponent(slug)}/assets`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("founder_token") ?? ""}` },
      }).then(r => r.json()).catch(() => []),
      fetch(`${api.base}/api/books/${encodeURIComponent(slug)}/qa`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("founder_token") ?? ""}` },
      }).then(r => r.json()).catch(() => []),
      api.approvals("").catch(() => [] as Approval[]),
    ]);
    setBook(b.product);
    setStory((b.story as Record<string, unknown>) ?? null);
    setBrief(undefined); setAssets(a); setQaReports(qa); setApprovals(p);
  };

  useEffect(() => { if (slug) { void load(); } }, [slug]);

  if (!slug) return <Shell title="Empty"><Empty title="Open from Products or Books" /></Shell>;
  if (book === undefined) return <Shell title="Loading…"><Spinner /></Shell>;
  if (!book) return <Shell title="Product not found"><ErrorBox error="No product with that slug" /></Shell>;

  const qaLatest = qaReports?.[0];

  return (
    <Shell title={book.title} subtitle={t("products.workspace_sub")}>
      {error && <ErrorBox error={error} />}

      <section className="card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="badge badge-gold mono">{book.slug}</span>
            <span className="badge badge-teal">{book.status}</span>
            <span className="muted text-xs mono">{(story as { pages?: unknown[] } | null)?.pages?.length ?? "—"} pages</span>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={() => startTransition(() => void load())}>
            {pending ? "…loading" : "Refresh"}
          </button>
        </div>
        {brief && (
          <div className="mt-3 rounded-xl border border-[color:var(--line)] p-3">
            <div className="eyebrow">{t("products.brief")} · {brief.status}</div>
            {brief.target_age && <div className="mt-1 text-sm">Ages {brief.target_age} · {brief.format} · {brief.page_count} pages · {brief.marketplace?.toUpperCase()}</div>}
          </div>
        )}
      </section>

      <div className="mt-4 grid lg:grid-cols-3 gap-4">
        {/* Illustrations */}
        <section className="card lg:col-span-1">
          <h3 className="eyebrow">{t("products.assets")}</h3>
          <div className="mt-3 grid grid-cols-3 gap-2">
            {(assets ?? []).map((a) => (
              <div key={a.asset_id} className="rounded-lg border border-[color:var(--line)] p-1.5 text-center">
                <div className="h-16 flex items-center justify-center text-2xl">🎨</div>
                <div className="muted text-[10px] truncate">p{a.page_number}</div>
              </div>
            ))}
            {assets && assets.length === 0 && <p className="muted text-xs col-span-3">No illustrations yet — build the book first.</p>}
          </div>
        </section>

        {/* QA Report */}
        <section className="card lg:col-span-2">
          <h3 className="eyebrow">{t("products.qa_reports")}</h3>
          {qaLatest ? (
            <div className="mt-3">
              <div className="flex items-center justify-between gap-2">
                <span className={`badge ${qaLatest.verdict.startsWith("PASS") ? "badge-ok" : qaLatest.verdict.startsWith("WARN") ? "badge-warn" : "badge-err"}`}>
                  {qaLatest.verdict}
                </span>
                <span className="muted text-[11px]">{qaLatest.created_at}</span>
              </div>
              <ul className="mt-2 max-h-56 space-y-1 overflow-y-auto text-[11px]">
                {qaLatest.checks.map((c, i) => (
                  <li key={i} className="flex items-center justify-between gap-2 rounded-lg border border-[color:var(--line)] px-2 py-1">
                    <span className="truncate">{c.name}</span>
                    <span className={c.ok ? "text-[color:var(--ok)]" : "text-[color:var(--err)]"}>{c.ok ? "✓" : "✕"}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="muted mt-3 text-sm">No QA report yet — run <code>qa_book {slug}</code>.</p>
          )}
        </section>
      </div>

      {/* Downloads */}
      <section className="card mt-4">
        <h3 className="eyebrow">Downloads</h3>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button className="btn btn-ghost" onClick={() => download("interior_kdp")}>
            📄 {t("products.download_interior")}
          </button>
          <button className="btn btn-ghost" onClick={() => download("pdf")}>
            📄 {t("products.download_square")}
          </button>
        </div>
        <button className="btn btn-gold mt-3 w-full justify-center" onClick={requestPublish}>
          {t("products.request_publish")} →
        </button>
      </section>

      {/* Linked approvals */}
      <section className="card mt-4">
        <h3 className="eyebrow">Approvals linked to this product</h3>
        <ul className="mt-2 divide-y divide-[color:var(--line)] text-sm">
          {approvals.filter(a => String(a.ref).includes(slug)).map(a => (
            <li key={a.approval_id} className="flex items-center justify-between gap-3 py-2">
              <span className="mono text-xs">#{a.approval_id} · {a.kind}</span>
              <span className={`badge ${a.status === "pending" ? "badge-warn" : a.status === "approved" ? "badge-ok" : "badge-err"}`}>
                {a.status}
              </span>
            </li>
          ))}
          {approvals.filter(a => String(a.ref).includes(slug)).length === 0 && <li className="muted py-3">No approvals yet.</li>}
        </ul>
        <Link href="/approvals" className="btn btn-ghost btn-sm mt-3 w-full justify-center">
          Open Approvals →
        </Link>
      </section>
    </Shell>
  );

  async function download(kind: "pdf" | "interior_kdp") {
    const token = localStorage.getItem("founder_token");
    const path = kind === "interior_kdp"
      ? `/api/books/${encodeURIComponent(slug)}/interior_kdp`
      : `/api/books/${encodeURIComponent(slug)}/pdf`;
    try {
      const resp = await fetch(`${api.base}${path}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) { setError(`Download failed — HTTP ${resp.status}`); return; }
      const blob = await resp.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${slug}${kind === "interior_kdp" ? "-kdp" : ""}.pdf`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      setError("Download failed");
    }
  }

  async function requestPublish() {
    try {
      await api.publishRequest(slug, "");
      setError(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    }
  }
}
