"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useLang } from "@/lib/lang";

const NAV = [
  { href: "/dashboard", key: "nav.dashboard", icon: "🏠" },
  { href: "/ceo", key: "nav.ceo", icon: "🤵" },
  { href: "/departments", key: "nav.departments", icon: "🏢" },
  { href: "/agents", key: "nav.agents", icon: "🪪" },
  { href: "/capabilities", key: "nav.capabilities", icon: "🧩" },
  { href: "/books", key: "nav.books", icon: "📚" },
  { href: "/products", key: "nav.products", icon: "📦" },
  { href: "/opportunities", key: "nav.opportunities", icon: "💰" },
  { href: "/approvals", key: "nav.approvals", icon: "✅" },
  { href: "/reports", key: "nav.reports", icon: "📄" },
  { href: "/observability", key: "nav.observability", icon: "📡" },
  { href: "/settings", key: "nav.settings", icon: "⚙️" },
] as const;

function TokenGate() {
  const [open, setOpen] = useState(false);
  const [token, setToken] = useState("");
  const [error, setError] = useState<string>("");
  const router = useRouter();

  useEffect(() => {
    if (!localStorage.getItem("founder_token")) {
      setOpen(true);     // أول زيارة: عرض لطيف — بدون رسالة خطأ
      return;
    }
    const on401 = () => { setError("Invalid founder token — re-enter it"); setOpen(true); };
    window.addEventListener("hq:unauthorized", on401);
    return () => window.removeEventListener("hq:unauthorized", on401);
  }, []);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="card w-full max-w-md fade-in">
        <div className="text-2xl font-bold">🔐 Founder Token</div>
        <p className="muted mt-1 text-sm">
          Every request to the API requires the token from <code>.env</code> — it never leaves your browser.
        </p>
        {error && <p className="mt-3 text-sm text-[color:var(--err)]">{error}</p>}
        <input
          className="input mt-4"
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

export default function Shell({ title, subtitle, actions, children }: {
  title: string; subtitle?: string; actions?: React.ReactNode; children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { lang, toggle, t } = useLang();

  return (
    <div className="flex min-h-screen">
      {/* Sidebar — full height, no bottom clutter */}
      <aside className="sticky top-0 h-screen w-[248px] shrink-0 border-e border-[color:var(--line)] bg-[color:var(--bg-soft)]/90 px-4 py-5 flex flex-col">
        <div className="px-2 pb-4 border-b border-[color:var(--line)]">
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-gradient-to-b from-[color:var(--gold)] to-[color:var(--gold-deep)] text-2xl shadow-lg">
              🏢
            </div>
            <div className="min-w-0">
              <div className="text-[17px] font-extrabold leading-tight truncate">AI Business <span className="text-[color:var(--gold)]">HQ</span></div>
              <div className="text-[10px] muted leading-4">{t("brand.tagline")}</div>
            </div>
          </div>
        </div>

        <nav className="mt-5 flex-1 flex flex-col gap-1 overflow-y-auto scrollbar-thin">
          {NAV.map((item) => (
            <Link key={item.href} href={item.href}
                  className={`nav-link ${pathname.startsWith(item.href) ? "active" : ""}`}>
              <span className="text-lg w-6 text-center shrink-0">{item.icon}</span>
              <span className="truncate">{t(item.key)}</span>
            </Link>
          ))}
        </nav>
      </aside>

      {/* Content column */}
      <main className="min-w-0 flex-1 flex flex-col">
        {/* Top bar — system status + language toggle */}
        <header className="flex items-center justify-between gap-3 border-b border-[color:var(--line)] px-6 py-2 text-[12px]">
          <div className="flex items-center gap-3 min-w-0">
            <span className="badge badge-ok !text-[11px] shrink-0">● LIVE</span>
            <span className="muted truncate hidden sm:inline">{t("brand.live")}</span>
            <span className="muted truncate hidden lg:inline">— {t("brand.gate")}</span>
          </div>
          <button onClick={toggle}
            className="rounded-lg border border-[color:var(--line)] px-3 py-1.5 text-[11px] font-semibold hover:bg-white/5 transition-colors shrink-0"
            aria-label="Toggle language">
            {lang === "en" ? "AR — العربية" : "EN — English"}
          </button>
        </header>

        {/* Page title bar */}
        <div className="flex items-center justify-between gap-4 px-6 py-4">
          <div className="min-w-0">
            <h1 className="text-2xl font-extrabold tracking-tight">{title}</h1>
            {subtitle && <p className="muted text-sm mt-0.5">{subtitle}</p>}
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </div>

        <div className="px-6 pb-6 flex-1">{children}</div>
      </main>

      <TokenGate />
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  const { t } = useLang();
  return (
    <div className="flex items-center gap-3 text-[color:var(--muted)] py-8">
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
    <div className="card flex flex-col items-center gap-2 py-12 text-center">
      <div className="text-5xl">{icon}</div>
      <div className="text-lg font-bold">{title}</div>
      {hint && <div className="muted text-sm max-w-md">{hint}</div>}
    </div>
  );
}
