import React from "react";

export default function MeetingsLoading() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      <section className="animate-pulse rounded-[2rem] border border-slate-200/80 bg-white/85 p-8 shadow-lg shadow-slate-200/60 backdrop-blur">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
          Meetings
        </h1>
        <p className="mt-3 text-sm text-slate-600">Loading meetings…</p>
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <div className="h-32 rounded-3xl bg-slate-200/80" />
          <div className="h-32 rounded-3xl bg-slate-200/80" />
        </div>
      </section>
    </main>
  );
}
