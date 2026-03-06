import React from "react";
import type { ReactNode } from "react";
import Link from "next/link";

import { LegalLinks } from "./LegalLinks";
import "./globals.css";

type LayoutProps = {
  children: ReactNode;
};

export default function RootLayout({ children }: LayoutProps) {
  return (
    <html lang="en" className="h-full bg-slate-950">
      <body className="min-h-full bg-[radial-gradient(circle_at_top,_rgba(14,165,233,0.12),_transparent_28%),linear-gradient(180deg,#f8fafc_0%,#e2e8f0_100%)] text-slate-900 antialiased">
        <div className="min-h-screen">
          <header className="border-b border-white/10 bg-slate-950/95 text-white shadow-lg shadow-slate-950/30 backdrop-blur">
            <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-5 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
              <div>
                <Link href="/" className="text-xl font-semibold tracking-tight text-white transition hover:text-cyan-200">
                  CouncilSense
                </Link>
                <p className="mt-1 max-w-2xl text-sm text-slate-300">
                  Clear, evidence-grounded local government updates for residents.
                </p>
              </div>
              <nav aria-label="Primary" className="flex flex-wrap items-center gap-2 text-sm font-medium">
                <Link
                  href="/meetings"
                  className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-slate-100 transition hover:border-cyan-300/40 hover:bg-cyan-400/10 hover:text-cyan-100"
                >
                  Meetings
                </Link>
                <Link
                  href="/settings"
                  className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-slate-100 transition hover:border-cyan-300/40 hover:bg-cyan-400/10 hover:text-cyan-100"
                >
                  Settings
                </Link>
              </nav>
            </div>
          </header>

          <div className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8 lg:py-10">
            {children}
          </div>

          <footer className="border-t border-slate-200/80 bg-white/75 backdrop-blur">
            <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-6 text-sm text-slate-600 sm:px-6 lg:px-8">
              <p className="font-medium text-slate-700">Public information for civic participation.</p>
              <LegalLinks label="Public legal links" />
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}