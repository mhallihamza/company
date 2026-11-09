import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Business HQ — AI Company Operating System",
  description:
    "An AI CEO that delegates to specialised departments (Books, Intelligence, Affiliate, Marketing, Finance, QA…) and asks your approval before any external action.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" dir="ltr">
      <body className="antialiased">{children}</body>
    </html>
  );
}
