import React from "react";
import Link from "next/link";

export default function TermsOfServicePage() {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-8">
      <section className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-lg shadow-slate-200/70 backdrop-blur sm:p-10">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Legal</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">
          Terms of service
        </h1>
        <p className="mt-3 text-sm text-slate-500">Last updated: March 7, 2026</p>
        <div className="mt-6 space-y-6 text-sm leading-7 text-slate-700 sm:text-base">
          <p>
            CouncilSense provides meeting summaries, evidence references, and settings controls to help
            residents follow public local government activity.
          </p>
          <p>
            The service is intended for informational use. Users should verify important decisions against
            source materials when confidence indicators or evidence references suggest additional review.
          </p>
          <p>
            By using the local or hosted app, you agree not to misuse the service, interfere with normal
            operation, or represent generated summaries as official government records.
          </p>
        </div>
      </section>

      <section className="flex flex-wrap items-center gap-4 text-sm font-medium text-cyan-800">
        <Link href="/privacy" className="transition hover:text-cyan-950 hover:underline">
          Review privacy policy
        </Link>
        <Link href="/" className="transition hover:text-cyan-950 hover:underline">
          Return to home
        </Link>
      </section>
    </main>
  );
}