"use client";

import { useEffect, useState } from "react";
import Shell, { Spinner, ErrorBox, Empty } from "@/components/Shell";
import { useLang } from "@/lib/lang";
import { api, type Book } from "@/lib/api";

const STATUS_LABEL: Record<string, [string, string]> = {
  story: ["📝 Story draft", "badge-warn"],
  images: ["🎨 Images ready", "badge-teal"],
  pdf: ["📄 PDF ready", "badge-teal"],
  qa: ["🛡 QA passed", "badge-ok"],
  candidate: ["🆕 Candidate", "badge-gold"],
  approved: ["✅ Approved", "badge-ok"],
  published: ["🚀 Published", "badge-ok"],
};

function statusBadge(status: string): [string, string] {
  return STATUS_LABEL[status] ?? [status, "badge"];
}

export default function BooksPage() {
  const { t } = useLang();
  const [books, setBooks] = useState<Book[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [idea, setIdea] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState("");

  const load = () => api.books().then(setBooks).catch((e) => setError(e instanceof Error ? e.message : "Could not load"));
  useEffect(() => { load(); }, []);

  async function downloadPdf(slug: string) {
    setMsg("");
    try {
      await api.downloadBook(slug);
      setMsg(`📄 ${slug}.pdf`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Download failed");
    }
  }

  async function createStory() {
    const text = idea.trim();
    if (!text || busy) return;
    setBusy("create"); setMsg("");
    try {
      const out = await api.createStory(text);
      setMsg(`✏️ Story ready: ${String(out.slug ?? "")}`);
      setIdea("");
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Story failed");
    } finally { setBusy(null); }
  }

  async function action(kind: "build" | "qa" | "publish", slug: string) {
    setBusy(`${kind}:${slug}`); setMsg("");
    try {
      if (kind === "build") {
        const out = await api.buildBook(slug);
        setMsg(`📐 ${String(out.summary ?? "Book built")}`);
      } else if (kind === "qa") {
        const out = await api.qaBook(slug);
        setMsg(`🛡 ${String((out as { summary?: string }).summary ?? JSON.stringify(out).slice(0, 120))}`);
      } else {
        const out = await api.publishRequest(slug, "Publish request from the HQ console");
        setMsg(`✋ Publish request #${out.approval_id} — see Approvals`);
      }
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Action failed");
    } finally { setBusy(null); }
  }

  return (
    <Shell title={t("books.title")} subtitle={t("books.subtitle")}>
      {error && <ErrorBox error={error} />}

      {/* New story */}
      <div className="card mb-6">
        <h2 className="font-bold text-lg">{t("books.new")}</h2>
        <div className="mt-2 flex gap-2 flex-col sm:flex-row">
          <input className="input flex-1" placeholder={t("books.new_placeholder")}
                 value={idea} onChange={(e) => setIdea(e.target.value)}
                 onKeyDown={(e) => e.key === "Enter" && createStory()} />
          <button className="btn btn-gold" onClick={createStory} disabled={busy === "create" || !idea.trim()}>
            {busy === "create" ? "…" : t("books.write")}
          </button>
        </div>
        {msg && <div className="mt-2 rounded-lg border border-[color:var(--line)] bg-black/30 p-3 text-sm">{msg}</div>}
      </div>

      {/* List */}
      {!books && !error && <Spinner />}
      {books && books.length === 0 && (
        <Empty icon="📚" title={t("books.empty")} hint={t("books.empty_hint")} />
      )}
      <div className="grid md:grid-cols-2 gap-4">
        {books?.map((b) => {
          const [label, cls] = statusBadge(b.status);
          return (
            <div key={b.slug} className="card flex flex-col">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-bold leading-6">{b.title}</h3>
                  <div className="muted text-[11px] font-mono mt-1 truncate" dir="ltr">{b.slug}</div>
                </div>
                <span className={`badge ${cls} shrink-0`}>{label}</span>
              </div>
              <div className="muted mt-2 flex items-center justify-between gap-2 text-[11px]">
                <span>{b.pdf_path ? `${t("books.pdf")} — ${b.pdf_path.split(/[\\/]/).pop()}` : "No PDF yet"}</span>
                {b.pdf_path && (
                  <button className="btn btn-ghost btn-sm" onClick={() => downloadPdf(b.slug)}>
                    ⬇ {t("books.pdf")}
                  </button>
                )}
              </div>
              <div className="mt-3 flex flex-wrap gap-2 border-t border-[color:var(--line)] pt-3">
                <button className="btn btn-ghost btn-sm" onClick={() => action("build", b.slug)} disabled={!!busy}>{t("books.build")}</button>
                <button className="btn btn-ghost btn-sm" onClick={() => action("qa", b.slug)} disabled={!!busy}>{t("books.check")}</button>
                <button className="btn btn-gold btn-sm" onClick={() => action("publish", b.slug)} disabled={!!busy || (b.status !== "pdf" && b.status !== "qa")}>{t("books.publish_request")}</button>
              </div>
            </div>
          );
        })}
      </div>
    </Shell>
  );
}
