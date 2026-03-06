import React from "react";

export default function MeetingDetailLoading() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-6">
      <section className="animate-pulse rounded-[2rem] border border-slate-200/80 bg-white/85 p-8 shadow-lg shadow-slate-200/60 backdrop-blur">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Meeting detail</h1>
        <p className="mt-3 text-sm text-slate-600">Loading meeting detail…</p>
        <div className="mt-6 h-24 rounded-3xl bg-slate-200/80" />
      </section>
    </main>
  );
}
