import Link from "next/link";
import { headers } from "next/headers";

import { apiGetJson, type MeetingDetailResponse } from "@/lib/councilsense";
import { RerunPanel } from "@/components/RerunPanel";

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

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

export default async function MeetingDetailPage(props: {
  params: Promise<{ meetingId: string }>;
}) {
  const { meetingId } = await props.params;
  let data: MeetingDetailResponse | null = null;
  let loadError: string | null = null;
  try {
    const base = await requestBaseUrl();
    data = await apiGetJson<MeetingDetailResponse>(
      `${base}/api/meetings/${encodeURIComponent(meetingId)}`,
    );
  } catch (e) {
    loadError = e instanceof Error ? e.message : String(e);
  }

  if (!data) {
    const isNotFound = (loadError || "").includes("(404)");
    return (
      <main className="space-y-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              Couldn’t load meeting
            </h1>
            <div className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
              {loadError}
            </div>
          </div>
          <Link
            href="/meetings"
            className="rounded-md px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-100 dark:text-zinc-200 dark:hover:bg-zinc-900"
          >
            ← Back
          </Link>
        </div>

        <div className="rounded-xl border border-zinc-200 bg-white p-5 text-sm text-zinc-700 shadow-sm dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-300">
          <div className="font-medium">
            {isNotFound ? "Meeting not found" : "Backend status"}
          </div>
          <div className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
            Expected backend URL:{" "}
            <span className="font-mono">{backendBase()}</span>
          </div>

          {isNotFound ? (
            <div className="mt-3 space-y-2">
              <div>
                That <span className="font-mono">meeting_id</span> isn’t present
                in the backend store.
              </div>
              <div>
                Go back to the meetings list and click an item, or re-import the
                packet.
              </div>
              <div className="mt-2 rounded-md bg-zinc-50 p-3 font-mono text-xs dark:bg-zinc-900/40">
                curl {backendBase()}/api/meetings
              </div>
            </div>
          ) : (
            <div className="mt-3">
              Start the backend:
              <div className="mt-2 rounded-md bg-zinc-50 p-3 font-mono text-xs dark:bg-zinc-900/40">
                python -m minutes_spike --store-dir out/meetings --serve
              </div>
            </div>
          )}
        </div>
      </main>
    );
  }

  const title = data.meeting.title ?? data.meeting.meeting_id;

  const artifacts = data.artifacts ?? {};
  const things = asArray(artifacts["things_you_care_about"]);
  const passA = asArray(artifacts["agenda_pass_a"]);
  const passC = asRecord(artifacts["meeting_pass_c"]);

  const meetingHighlights = asArray(passC["highlights"]);
  const watchlistHits = asArray(passC["watchlist_hits"]);

  return (
    <main className="space-y-8">
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
            <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-zinc-600 dark:text-zinc-400">
              {data.meeting.meeting_date ? (
                <span>{data.meeting.meeting_date}</span>
              ) : null}
              {data.meeting.meeting_location ? (
                <span className="truncate">
                  {data.meeting.meeting_location}
                </span>
              ) : null}
              <span>Imported: {data.meeting.imported_at}</span>
              <span className="font-mono text-xs">
                {data.meeting.meeting_id}
              </span>
            </div>
          </div>
          <Link
            href="/meetings"
            className="rounded-md px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-100 dark:text-zinc-200 dark:hover:bg-zinc-900"
          >
            ← Back
          </Link>
        </div>

        <div className="flex flex-wrap gap-2 text-xs">
          <a
            className="rounded-md border border-zinc-200 bg-white px-2 py-1 hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:bg-zinc-900"
            href={data.raw.meeting_json}
            target="_blank"
            rel="noreferrer"
          >
            meeting.json
          </a>
          <a
            className="rounded-md border border-zinc-200 bg-white px-2 py-1 hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:bg-zinc-900"
            href={data.raw.things_you_care_about_json}
            target="_blank"
            rel="noreferrer"
          >
            things_you_care_about.json
          </a>
          <a
            className="rounded-md border border-zinc-200 bg-white px-2 py-1 hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:bg-zinc-900"
            href={data.raw.agenda_pass_a_json}
            target="_blank"
            rel="noreferrer"
          >
            agenda_pass_a.json
          </a>
          <a
            className="rounded-md border border-zinc-200 bg-white px-2 py-1 hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:bg-zinc-900"
            href={data.raw.meeting_pass_c_json}
            target="_blank"
            rel="noreferrer"
          >
            meeting_pass_c.json
          </a>
        </div>
      </div>

      <RerunPanel meetingId={data.meeting.meeting_id} />

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Meeting summary</h2>
        {Object.keys(passC).length === 0 ? (
          <div className="rounded-lg border border-zinc-200 bg-white p-5 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400">
            No meeting-level summary yet. Run Pass C in the backend.
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
              <div className="text-sm font-medium">Highlights</div>
              <div className="mt-3 space-y-3">
                {meetingHighlights.length === 0 ? (
                  <div className="text-sm text-zinc-600 dark:text-zinc-400">
                    No highlights.
                  </div>
                ) : (
                  meetingHighlights.slice(0, 12).map((h, idx) => {
                    const rec = asRecord(h);
                    return (
                      <div
                        key={idx}
                        className="rounded-md bg-zinc-50 p-3 dark:bg-zinc-900/40"
                      >
                        <div className="text-sm font-medium">
                          {String(rec["title"] ?? "")}
                        </div>
                        <div className="mt-1 text-sm text-zinc-700 dark:text-zinc-300">
                          {String(rec["why"] ?? "")}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
            <div className="rounded-lg border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
              <div className="text-sm font-medium">Watchlist</div>
              <div className="mt-3 space-y-2">
                {watchlistHits.length === 0 ? (
                  <div className="text-sm text-zinc-600 dark:text-zinc-400">
                    No watchlist hits.
                  </div>
                ) : (
                  watchlistHits.slice(0, 20).map((hit, idx) => {
                    const rec = asRecord(hit);
                    const category = String(rec["category"] ?? "");
                    const count = rec["count"];
                    return (
                      <div
                        key={idx}
                        className="flex items-center justify-between rounded-md bg-zinc-50 px-3 py-2 text-sm dark:bg-zinc-900/40"
                      >
                        <span className="font-medium">{category}</span>
                        <span className="text-zinc-600 dark:text-zinc-400">
                          {typeof count === "number"
                            ? count
                            : String(count ?? "")}
                        </span>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        )}
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Things you care about</h2>
          <div className="text-xs text-zinc-500 dark:text-zinc-400">
            {things.length} item(s)
          </div>
        </div>

        {things.length === 0 ? (
          <div className="rounded-lg border border-zinc-200 bg-white p-5 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400">
            No highlights yet. Run Pass B in the backend.
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {things.slice(0, 24).map((t, idx) => {
              const rec = asRecord(t);
              const evidence = asArray(rec["evidence"]);
              const firstEv = asRecord(evidence[0]);
              const snippet = String(firstEv["snippet"] ?? "");

              return (
                <div
                  key={idx}
                  className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-950"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold">
                        {String(rec["title"] ?? "")}
                      </div>
                      <div className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
                        {String(rec["category"] ?? "")}
                      </div>
                    </div>
                    <div className="shrink-0 rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-700 dark:bg-zinc-800 dark:text-zinc-200">
                      {typeof rec["confidence"] === "number"
                        ? (rec["confidence"] as number).toFixed(2)
                        : String(rec["confidence"] ?? "")}
                    </div>
                  </div>

                  <div className="mt-3 text-sm text-zinc-700 dark:text-zinc-300">
                    {String(rec["why"] ?? "")}
                  </div>

                  {snippet ? (
                    <div className="mt-3 rounded-md bg-zinc-50 p-3 text-sm text-zinc-700 dark:bg-zinc-900/40 dark:text-zinc-200">
                      <div className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                        Evidence
                      </div>
                      <div className="mt-1">{snippet}</div>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Agenda item summaries</h2>
          <div className="text-xs text-zinc-500 dark:text-zinc-400">
            {passA.length} item(s)
          </div>
        </div>

        {passA.length === 0 ? (
          <div className="rounded-lg border border-zinc-200 bg-white p-5 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400">
            No Pass A summaries yet. Run Pass A in the backend.
          </div>
        ) : (
          <div className="space-y-4">
            {passA.slice(0, 50).map((item, idx) => {
              const rec = asRecord(item);
              const passARec = asRecord(rec["pass_a"]);
              const summary = asArray(passARec["summary"]).map((s) =>
                String(s),
              );
              const citations = asArray(passARec["citations"]).map((s) =>
                String(s),
              );

              return (
                <div
                  key={idx}
                  className="rounded-lg border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950"
                >
                  <div className="text-sm font-semibold">
                    <span className="font-mono text-xs text-zinc-500 dark:text-zinc-400">
                      {String(rec["item_id"] ?? "")}
                    </span>
                    <span className="ml-2">{String(rec["title"] ?? "")}</span>
                  </div>

                  {summary.length > 0 ? (
                    <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-zinc-700 dark:text-zinc-300">
                      {summary.slice(0, 8).map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  ) : null}

                  {citations.length > 0 ? (
                    <div className="mt-3 rounded-md bg-zinc-50 p-3 text-sm text-zinc-700 dark:bg-zinc-900/40 dark:text-zinc-200">
                      <div className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                        Citations
                      </div>
                      <div className="mt-1 space-y-2">
                        {citations.slice(0, 3).map((c, i) => (
                          <div
                            key={i}
                            className="border-l-2 border-zinc-300 pl-3 dark:border-zinc-700"
                          >
                            {c}
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
      </section>

      <div className="text-xs text-zinc-500 dark:text-zinc-400">
        Backend:{" "}
        <code className="rounded bg-zinc-100 px-1 py-0.5 dark:bg-zinc-800">
          {backendBase()}
        </code>
      </div>
    </main>
  );
}
