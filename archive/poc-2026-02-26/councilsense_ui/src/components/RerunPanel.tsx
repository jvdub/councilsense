"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

type RerunResponse = {
  meeting_id?: string;
  generated_at?: string | null;
  ran_pass_a?: boolean;
  ran_pass_b?: boolean;
  ran_pass_c?: boolean;
  error?: string;
};

export function RerunPanel(props: { meetingId: string }) {
  const router = useRouter();
  const [profile, setProfile] = useState<string>("");
  const [passA, setPassA] = useState(false);
  const [passB, setPassB] = useState(true);
  const [passC, setPassC] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RerunResponse | null>(null);

  const canRun = useMemo(() => {
    return !busy && (passA || passB || passC);
  }, [busy, passA, passB, passC]);

  async function run() {
    setError(null);
    setResult(null);

    if (!canRun) return;

    setBusy(true);
    try {
      const body = {
        profile: profile.trim() || undefined,
        summarize_all_items: passA,
        classify_relevance: passB,
        summarize_meeting: passC,
      };

      const res = await fetch(
        `/api/meetings/${encodeURIComponent(props.meetingId)}/rerun`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );

      const payload = (await res.json().catch(() => ({}))) as RerunResponse;
      if (!res.ok) {
        throw new Error(payload.error || `Re-run failed (${res.status})`);
      }

      setResult(payload);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-3 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold">Re-run analysis</h2>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Triggers Pass A/B/C on the backend and refreshes this page.
          </p>
        </div>
        <button
          type="button"
          disabled={!canRun}
          onClick={run}
          className="rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
        >
          {busy ? "Running…" : "Run"}
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <div className="text-sm font-medium">Options</div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={passA}
              onChange={(e) => setPassA(e.target.checked)}
            />
            <span>Pass A (summarize agenda items)</span>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={passB}
              onChange={(e) => setPassB(e.target.checked)}
            />
            <span>Pass B (things you care about)</span>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={passC}
              onChange={(e) => setPassC(e.target.checked)}
            />
            <span>Pass C (meeting summary)</span>
          </label>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Tip: Pass A requires an LLM model configured in your profile.
          </p>
        </div>

        <div className="space-y-2">
          <div className="text-sm font-medium">Profile (optional)</div>
          <input
            value={profile}
            onChange={(e) => setProfile(e.target.value)}
            placeholder="/path/to/profile.yaml"
            className="w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-zinc-300 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:ring-zinc-700"
          />
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Leave blank to use the backend’s default resolved profile.
          </p>
        </div>
      </div>

      {error ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900/40 dark:bg-red-950/40 dark:text-red-200">
          {error}
        </div>
      ) : null}

      {result ? (
        <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-800 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-200">
          <div className="font-medium">Completed</div>
          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-600 dark:text-zinc-400">
            {result.generated_at ? <span>{result.generated_at}</span> : null}
            <span>Pass A: {String(!!result.ran_pass_a)}</span>
            <span>Pass B: {String(!!result.ran_pass_b)}</span>
            <span>Pass C: {String(!!result.ran_pass_c)}</span>
          </div>
        </div>
      ) : null}
    </section>
  );
}
