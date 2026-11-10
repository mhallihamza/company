"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useLang, type DictKey } from "@/lib/lang";

type NavItem = { href: string; key: DictKey; icon: string };

const NAV: { section: DictKey; items: NavItem[] }[] = [
  {
    section: "nav.group_company",
    items: [
      { href: "/dashboard", key: "nav.dashboard", icon: "◉" },
      { href: "/ceo", key: "nav.ceo", icon: "◆" },
      { href: "/departments", key: "nav.departments", icon: "▣" },
      { href: "/agents", key: "nav.agents", icon: "▤" },
      { href: "/capabilities", key: "nav.capabilities", icon: "⬡" },
    ],
  },
  {
    section: "nav.group_output",
    items: [
      { href: "/books", key: "nav.books", icon: "▤" },
      { href: "/products", key: "nav.products", icon: "▲" },
      { href: "/opportunities", key: "nav.opportunities", icon: "◇" },
      { href: "/profiles", key: "nav.profiles", icon: "◎" },
      { href: "/approvals", key: "nav.approvals", icon: "✓" },
      { href: "/reports", key: "nav.reports", icon: "▧" },
    ],
  },
  {
    section: "nav.group_system",
    items: [
      { href: "/observability", key: "nav.observability", icon: "◉" },
      { href: "/settings", key: "nav.settings", icon: "⚙" },
    ],
  },
];

function TokenGate() {
  const [open, setOpen] = useState(false);
  const [token, setToken] = useState("");
  const [error, setError] = useState<string>("");
  const router = useRouter();

  useEffect(() => {
    if (!localStorage.getItem("founder_token")) {
      setOpen(true);     // first visit: gentle prompt — no error message
      return;
    }
    const on401 = () => { setError("Invalid founder token — re-enter it"); setOpen(true); };
    window.addEventListener("hq:unauthorized", on401);
    return () => window.removeEventListener("hq:unauthorized", on401);
  }, []);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md">
      <div className="card w-full max-w-md fade-in mx-4">
        <div className="eyebrow">Security gate</div>
        <div className="text-2xl font-extrabold mt-2">Founder Token</div>
        <p className="muted mt-1 text-sm">
          Every request to the API requires the token from <code className="mono">.env</code> — it never leaves your browser.
        </p>
        {error && <p className="mt-3 text-sm" style={{ color: "var(--err)" }}>{error}</p>}
        <input
          className="input mt-4 mono"
          type="password"
          placeholder="FOUNDER_TOKEN"
          value={token}
          autoFocus
          onChange={(e) => setToken(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && save()}
        />
        <div className="mt-4 flex gap-2">
          <button className="btn btn-gold flex-1 justify-center" onClick={save}>Authenticate</button>
        </div>
      </div>
    </div>
  );

  function save() {
    if (!token.trim()) return;
    localStorage.setItem("founder_token", token.trim());
    setOpen(false);
    setError("");
    router.refresh();
  }
}

function LogoMark() {
  return (
    <div
      aria-hidden="true"
      className="relative grid h-11 w-11 shrink-0 place-items-center rounded-[14px] text-[15px] font-black tracking-[-0.04em] text-[#2a1f08] select-none"
      style={{
        background: "linear-gradient(160deg, #f6dc9d 0%, #e9c46a 45%, #caa050 100%)",
        boxShadow: "0 10px 24px rgba(202,160,80,0.35), inset 0 1px 0 rgba(255,255,255,0.7)",
      }}
    >
      HQ
      <span className="absolute -bottom-1 -end-1 h-3 w-3 rounded-full" style={{ background: "var(--ok)", border: "2px solid var(--bg-soft)" }} />
    </div>
  );
}

export default function Shell({ title, subtitle, actions, children }: {
  title: string; subtitle?: string; actions?: React.ReactNode; children: React.ReactNode;
}) {
  const pathname = usePathname() ?? "";
  const { lang, toggle, t } = useLang();

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="sticky top-0 h-screen w-[248px] shrink-0 border-e border-[color:var(--line)] bg-[color:var(--bg-soft)]/90 px-4 py-5 hidden md:flex flex-col">
        <div className="px-2 pb-4 border-b border-[color:var(--line)]">
          <div className="flex items-center gap-3">
            <LogoMark />
            <div className="min-w-0">
              <div className="text-[16px] font-extrabold leading-tight truncate tracking-[-0.02em]">AI Business <span className="text-[color:var(--gold)]">HQ</span></div>
              <div className="text-[9.5px] muted leading-4 tracking-wide">{t("brand.tagline")}</div>
            </div>
          </div>
        </div>

        <nav className="mt-4 flex-1 flex flex-col gap-0.5 overflow-y-auto scrollbar-thin" aria-label="Main navigation">
          {NAV.map((group) => (
            <div key={group.section}>
              <div className="nav-section">{t(group.section)}</div>
              {group.items.map((item) => {
                const active = pathname.startsWith(item.href);
                return (
                  <Link key={item.href} href={item.href}
                        className={`nav-link ${active ? "active" : ""}`}
                        aria-current={active ? "page" : undefined}>
                    <span className="w-5 text-center shrink-0 text-[12px] opacity-80">{item.icon}</span>
                    <span className="truncate">{t(item.key)}</span>
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="border-t border-[color:var(--line)] pt-3 px-2">
          <div className="flex items-center justify-between gap-2 text-[10px] muted">
            <span className="mono">v3.2.0</span>
            <span className="truncate">{t("dash.brand_internal")}</span>
          </div>
        </div>
      </aside>

      {/* Content column */}
      <main className="min-w-0 flex-1 flex flex-col">
        {/* Top status bar */}
        <header className="flex items-center justify-between gap-3 border-b border-[color:var(--line)] px-5 py-2 text-[11.5px]">
          <div className="flex items-center gap-3 min-w-0">
            <span className="flex items-center gap-2 shrink-0">
              <span className="status-dot" />
              <span className="font-semibold text-[color:var(--ok)]">{t("dash.operational")}</span>
            </span>
            <span className="muted truncate hidden lg:inline">{t("brand.gate")}</span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="badge badge-teal !text-[10px] mono hidden sm:inline-flex">FOUNDER</span>
            <button onClick={toggle}
              className="rounded-lg border border-[color:var(--line)] px-3 py-1.5 text-[11px] font-semibold hover:bg-white/5 transition-colors"
              aria-label="Toggle language">
              {lang === "en" ? "AR — العربية" : "EN — English"}
            </button>
          </div>
        </header>

        {/* Page title bar */}
        <div className="flex items-center justify-between gap-4 px-5 sm:px-6 pt-5 pb-4">
          <div className="min-w-0">
            <h1 className="text-[22px] sm:text-2xl font-extrabold tracking-[-0.03em] leading-tight">{title}</h1>
            {subtitle && <p className="muted text-[12.5px] mt-1 leading-snug">{subtitle}</p>}
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </div>

        <div className="px-5 sm:px-6 pb-6 flex-1">{children}</div>
      </main>

      <TokenGate />
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  const { t } = useLang();
  return (
    <div className="flex items-center gap-3 text-[color:var(--muted)] py-10">
      <span className="inline-block h-5 w-5 rounded-full border-2 border-[color:var(--gold)] border-t-transparent spin" />
      <span>{label ?? t("common.loading")}</span>
    </div>
  );
}

export function ErrorBox({ error }: { error: string }) {
  return (
    <div className="rounded-xl border border-[color:var(--err)]/40 bg-[color:var(--err)]/10 px-4 py-3 text-sm text-[color:var(--err)]">
      {error}
    </div>
  );
}

export function Empty({ icon = "🗂️", title, hint }: { icon?: string; title: string; hint?: string }) {
  return (
    <div className="card flex flex-col items-center gap-3 py-14 text-center">
      <div className="text-5xl opacity-90">{icon}</div>
      <div className="text-lg font-bold">{title}</div>
      {hint && <div className="muted text-sm max-w-md">{hint}</div>}
    </div>
  );
}
