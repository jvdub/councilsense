import React from "react";
import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-8 lg:gap-10">
      <section className="overflow-hidden rounded-[2rem] border border-slate-200/70 bg-slate-950 px-6 py-10 text-white shadow-2xl shadow-slate-400/20 sm:px-8 lg:px-10 lg:py-14">
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1.4fr)_minmax(18rem,1fr)] lg:items-center">
          <div className="space-y-6">
            <div className="inline-flex rounded-full border border-cyan-300/20 bg-cyan-400/10 px-4 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-cyan-200">
              Local government clarity
            </div>
            <div className="space-y-4">
              <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-white sm:text-5xl">
                CouncilSense
              </h1>
              <p className="max-w-3xl text-lg leading-8 text-slate-300">
                Stay informed about your local government meetings with concise summaries,
                notable topics, and evidence-backed details that help residents follow what
                happened and what comes next.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Link
                href="/meetings"
                className="inline-flex items-center justify-center rounded-full bg-cyan-400 px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
              >
                Go to meetings
              </Link>
              <Link
                href="/settings"
                className="inline-flex items-center justify-center rounded-full border border-white/15 bg-white/5 px-6 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
              >
                Manage alerts
              </Link>
            </div>
          </div>

          <div className="grid gap-4">
            <div className="rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur-sm">
              <p className="text-sm font-medium text-cyan-200">Designed for residents</p>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                Follow agendas, decisions, and actions without digging through long minutes.
              </p>
            </div>
            <div className="rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur-sm">
              <p className="text-sm font-medium text-cyan-200">Evidence-first summaries</p>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                Confidence indicators and evidence references help you verify important claims.
              </p>
            </div>
            <div className="rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur-sm">
              <p className="text-sm font-medium text-cyan-200">Practical updates</p>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                See what was approved, what staff must do next, and which topics deserve attention.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <article className="rounded-3xl border border-slate-200/80 bg-white/85 p-6 shadow-lg shadow-slate-200/60 backdrop-blur">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Meetings feed</p>
          <h2 className="mt-3 text-xl font-semibold text-slate-900">Track recent activity</h2>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            Browse recent meetings, then open a detail view for summaries, decisions, actions, and evidence.
          </p>
        </article>
        <article className="rounded-3xl border border-slate-200/80 bg-white/85 p-6 shadow-lg shadow-slate-200/60 backdrop-blur">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Confidence flags</p>
          <h2 className="mt-3 text-xl font-semibold text-slate-900">Know when to verify</h2>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            Low-confidence results are highlighted so you can double-check evidence before sharing or acting.
          </p>
        </article>
        <article className="rounded-3xl border border-slate-200/80 bg-white/85 p-6 shadow-lg shadow-slate-200/60 backdrop-blur">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Resident controls</p>
          <h2 className="mt-3 text-xl font-semibold text-slate-900">Choose your updates</h2>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            Configure your home city, notifications, export requests, and deletion preferences in one place.
          </p>
        </article>
      </section>
    </main>
  );
}
