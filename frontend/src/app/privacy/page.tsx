import React from "react";
import Link from "next/link";

export default function PrivacyPolicyPage() {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-8">
      <section className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-lg shadow-slate-200/70 backdrop-blur sm:p-10">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Legal</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">
          Privacy policy
        </h1>
        <p className="mt-3 text-sm text-slate-500">Last updated: March 7, 2026</p>
        <div className="mt-6 space-y-6 text-sm leading-7 text-slate-700 sm:text-base">
          <p>
            CouncilSense stores account, city preference, and notification settings needed to deliver
            meeting updates and support resident self-service controls.
          </p>
          <p>
            We use the minimum information required to operate the service, including authentication
            identifiers, selected city, notification preferences, and governance workflow records for
            export or deletion requests.
          </p>
          <p>
            Meeting content shown in the app comes from public government sources. Resident account data
            is used only to personalize access, settings, and delivery behavior inside CouncilSense.
          </p>
        </div>
      </section>

      <section className="flex flex-wrap items-center gap-4 text-sm font-medium text-cyan-800">
        <Link href="/terms" className="transition hover:text-cyan-950 hover:underline">
          Review terms of service
        </Link>
        <Link href="/" className="transition hover:text-cyan-950 hover:underline">
          Return to home
        </Link>
      </section>
    </main>
  );
}