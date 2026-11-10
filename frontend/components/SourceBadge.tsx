"use client";

/**
 * Tiny inline badge for data provenance — every card / row must carry one.
 * `live` = real API data · `partial` = some fields missing · `demo` = stubbed.
 */
export default function SourceBadge({ source }: { source?: string }) {
  if (!source) return <span className="badge badge-gold !text-[10px]">LIVE</span>;
  const s = source.toLowerCase();
  if (s === "live") return <span className="badge badge-ok !text-[10px]">🟢 LIVE</span>;
  if (s === "partial") return <span className="badge badge-warn !text-[10px]">🟡 PARTIAL</span>;
  return <span className="badge badge-err !text-[10px]">🔴 DEMO</span>;
}
