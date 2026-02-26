import Link from "next/link";
import { headers } from "next/headers";

import { apiGetJson, type MeetingListResponse } from "@/lib/councilsense";

export const dynamic = "force-dynamic";

function backendBase() {
  return process.env.COUNCILSENSE_BACKEND_URL ?? "http://127.0.0.1:8000";
}

async function requestBaseUrl() {
  const h = await headers();
  const host = h.get("host");
  const proto = h.get("x-forwarded-proto") ?? "http";
  if (!host) return "http://localhost";
  return `${proto}://${host}`;
}

export default async function MeetingsPage() {
  let meetings: MeetingListResponse["meetings"] = [];
  let loadError: string | null = null;
  try {
    const base = await requestBaseUrl();
    const data = await apiGetJson<MeetingListResponse>(`${base}/api/meetings`);
    meetings = data.meetings ?? [];
  } catch (e) {
    loadError = e instanceof Error ? e.message : String(e);
  }

  return (
    <main className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Meetings</h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Imported packets and analysis artifacts.
          </p>
        </div>
        <Link
          href="/upload"
          className="rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
        >
          Upload a packet
        </Link>
      </div>

      <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
        <div className="divide-y divide-zinc-200 dark:divide-zinc-800">
          {loadError ? (
            <div className="p-6 text-sm text-zinc-700 dark:text-zinc-300">
              <div className="font-medium">Couldn’t load meetings.</div>
              <div className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
                {loadError}
              </div>
              <div className="mt-3 text-sm text-zinc-700 dark:text-zinc-300">
                Make sure the backend is running:
                <div className="mt-2 rounded-md bg-zinc-50 p-3 font-mono text-xs dark:bg-zinc-900/40">
                  python -m minutes_spike --store-dir out/meetings --serve
                </div>
              </div>
            </div>
          ) : meetings.length === 0 ? (
            <div className="p-6 text-sm text-zinc-600 dark:text-zinc-400">
              No meetings yet. Upload a PDF to get started.
            </div>
          ) : (
            meetings.map((m) => {
              const title = m.title ?? m.meeting_id;
              const date = m.meeting_date ?? "";
              const loc = m.meeting_location ?? "";
              const badges = m.badges ?? {};
              const badgeList = [
                badges.pass_a ? "Pass A" : null,
                badges.pass_b ? "Pass B" : null,
                badges.pass_c ? "Pass C" : null,
              ].filter(Boolean) as string[];

              return (
                <Link
                  key={m.meeting_id}
                  href={`/meetings/${encodeURIComponent(m.meeting_id)}`}
                  className="block p-5 hover:bg-zinc-50 dark:hover:bg-zinc-900/40"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <div className="truncate text-sm font-medium">
                          {title}
                        </div>
                        {badgeList.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {badgeList.map((b) => (
                              <span
                                key={b}
                                className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-700 dark:bg-zinc-800 dark:text-zinc-200"
                              >
                                {b}
                              </span>
                            ))}
                          </div>
                        ) : null}
                      </div>
                      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-600 dark:text-zinc-400">
                        {date ? <span>{date}</span> : null}
                        {loc ? <span className="truncate">{loc}</span> : null}
                        <span className="truncate">
                          Imported: {m.imported_at}
                        </span>
                      </div>
                    </div>
                    <div className="shrink-0 text-xs text-zinc-500 dark:text-zinc-400">
                      View →
                    </div>
                  </div>
                </Link>
              );
            })
          )}
        </div>
      </div>

      <div className="text-xs text-zinc-500 dark:text-zinc-400">
        Backend:{" "}
        <code className="rounded bg-zinc-100 px-1 py-0.5 dark:bg-zinc-800">
          {backendBase()}
        </code>
      </div>
    </main>
  );
}
