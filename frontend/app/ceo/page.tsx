"use client";

import { useEffect, useRef, useState } from "react";
import Shell from "@/components/Shell";
import { useLang } from "@/lib/lang";
import { api, type CeoOut, type Settings } from "@/lib/api";

type Msg = {
  role: "user" | "ceo";
  text: string;
  out?: CeoOut;
  at: string;
};

const EXAMPLES = [
  "Analyze the children’s-book market",
  "Write a story about a turtle who loves to draw",
  "Find affiliate products for my book niche",
  "What is the margin on a $9.99 book with 24 pages?",
  "Prepare a go-to-market pack for ‘Nutty the Seagull’",
  "Run QA on the latest book",
];

export default function CeoPage() {
  const { t } = useLang();
  const [messages, setMessages] = useState<Msg[]>([
    { role: "ceo", text: "Hello — I’m the CEO. Delegate anything you want, I’ll route it to the right department and report back. Nothing external happens without your approval.", at: now() },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [settings, setSettings] = useState<Settings | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { api.settings().then(setSettings).catch(() => setSettings(null)); }, []);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  async function send(text?: string) {
    const task = (text ?? input).trim();
    if (!task || busy) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [...m, { role: "user", text: task, at: now() }]);
    try {
      const out = await api.ceoRun(task);
      setMessages((m) => [...m, {
        role: "ceo",
        text: out.summary ?? out.error ?? "Task complete.",
        out, at: now(),
      }]);
    } catch (e) {
      setMessages((m) => [...m, {
        role: "ceo",
        text: e instanceof Error ? e.message : "Could not reach the server",
        at: now(),
      }]);
    } finally { setBusy(false); }
  }

  return (
    <Shell title={t("ceo.title")} subtitle={t("ceo.subtitle")}>
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Conversation */}
        <div className="card lg:col-span-2 flex flex-col min-h-[70vh]">
          <div className="flex flex-wrap gap-2 mb-4">
            {EXAMPLES.map((e) => (
              <button key={e} className="btn btn-ghost btn-sm" onClick={() => send(e)} disabled={busy}>{e}</button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto scrollbar-thin space-y-4 max-h-[52vh] pe-1">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"} fade-in`}>
                <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-7 ${
                  m.role === "user"
                    ? "bg-[color:var(--gold)]/90 text-[#241b08] rounded-tl-sm"
                    : "bg-white/5 border border-[color:var(--line)] rounded-tr-sm"}`}>
                  {m.role === "ceo" && (
                    <div className="mb-1 flex items-center gap-2 text-[11px] text-[color:var(--gold)]">
                      🤵 CEO
                      {m.out?.domain && <span className="badge badge-teal !text-[10px]">{m.out.domain}</span>}
                    </div>
                  )}
                  <div className="whitespace-pre-wrap">{m.text}</div>

                  {m.out?.artifacts && Object.keys(m.out.artifacts).length > 0 && (
                    <div className="mt-2 rounded-lg border border-[color:var(--line)] bg-black/20 p-2 text-[11px] text-[color:var(--muted)]">
                      <div className="mb-1 font-bold text-[color:var(--text)]">Artifacts</div>
                      {Object.entries(m.out.artifacts).map(([k, v]) => (
                        <div key={k} className="flex justify-between gap-2"><span>{k}</span><span className="font-mono text-[10px] truncate max-w-[60%]">{String(v)}</span></div>
                      ))}
                    </div>
                  )}
                  {m.out?.llm_note && <div className="mt-2 text-[11px] text-[color:var(--muted)]">🩺 {m.out.llm_note}</div>}
                  {m.out?.needs_approval && (
                    <div className="mt-2 rounded-lg border border-[color:var(--warn)]/40 bg-[color:var(--warn)]/10 p-2 text-[12px]">
                      ⚠️ This needs your sign-off — open <a href="/approvals" className="underline text-[color:var(--warn)]">Approvals</a>.
                    </div>
                  )}
                </div>
              </div>
            ))}
            {busy && (
              <div className="flex justify-start fade-in">
                <div className="rounded-2xl border border-[color:var(--line)] bg-white/5 px-4 py-3 text-sm">
                  <span className="inline-flex items-center gap-2 text-[color:var(--muted)]">
                    <span className="inline-block h-4 w-4 rounded-full border-2 border-[color:var(--gold)] border-t-transparent spin" />
                    CEO is routing…
                  </span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="mt-4 flex gap-2">
            <input className="input flex-1" placeholder={t("ceo.placeholder")}
                   value={input} onChange={(e) => setInput(e.target.value)}
                   onKeyDown={(e) => e.key === "Enter" && send()} disabled={busy} />
            <button className="btn btn-gold" onClick={() => send()} disabled={busy || !input.trim()}>{t("ceo.send")}</button>
          </div>
        </div>

        {/* Side panel */}
        <div className="space-y-4">
          <div className="card">
            <div className="muted text-xs mb-2">{t("ceo.autonomy")}</div>
            {settings ? (
              <>
                <div className="text-4xl font-extrabold text-[color:var(--gold)]">L{settings.autonomy_level}</div>
                <div className="mt-2 text-sm font-bold">{settings.autonomy_levels.find(l => l.level === settings.autonomy_level)?.name}</div>
                <p className="muted mt-1 text-xs leading-6">{settings.autonomy_levels.find(l => l.level === settings.autonomy_level)?.describe}</p>
              </>
            ) : <div className="muted text-sm">Loading…</div>}
          </div>

          <div className="card">
            <div className="muted text-xs mb-2">{t("ceo.rules")}</div>
            <ul className="text-sm leading-7 space-y-1 text-[color:var(--muted)]">
              <li>✅ {t("ceo.rule_1")}</li>
              <li>✅ {t("ceo.rule_2")}</li>
              <li>✅ {t("ceo.rule_3")}</li>
              <li>✅ {t("ceo.rule_4")}</li>
            </ul>
          </div>

          <a href="/settings" className="card block hover:border-[color:var(--gold)] transition-colors">
            <div className="font-bold">{t("nav.settings")}</div>
            <div className="muted text-xs mt-1">{settings?.llm_mode} · {settings?.db_backend}</div>
          </a>
        </div>
      </div>
    </Shell>
  );
}

function now() {
  return new Date().toLocaleTimeString("en", { hour: "2-digit", minute: "2-digit" });
}
