"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useMemo, useState } from "react";

type ImportResponse = {
  meeting_id?: string;
  redirect?: string;
  error?: string;
};

export default function UploadPage() {
  const router = useRouter();
  const [pdf, setPdf] = useState<File | null>(null);
  const [text, setText] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = useMemo(() => {
    return !submitting && (!!pdf || !!text);
  }, [submitting, pdf, text]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (!pdf && !text) {
      setError("Select a PDF (and optionally a text minutes file).");
      return;
    }

    const form = new FormData();
    if (pdf) form.append("pdf", pdf, pdf.name);
    if (text) form.append("text", text, text.name);

    setSubmitting(true);
    try {
      const res = await fetch("/api/import", {
        method: "POST",
        body: form,
      });

      const payload = (await res.json().catch(() => ({}))) as ImportResponse;
      if (!res.ok) {
        throw new Error(payload.error || `Import failed (${res.status})`);
      }

      const meetingId = payload.meeting_id;
      if (!meetingId) {
        throw new Error("Import succeeded but response is missing meeting_id");
      }

      router.push(`/meetings/${encodeURIComponent(meetingId)}`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Upload a meeting packet
        </h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Upload a PDF packet (required) and optional text minutes.
        </p>
      </div>

      <form
        onSubmit={onSubmit}
        className="space-y-4 rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950"
      >
        <div className="space-y-1">
          <label className="block text-sm font-medium">PDF packet</label>
          <input
            type="file"
            accept="application/pdf,.pdf"
            onChange={(e) => setPdf(e.target.files?.[0] ?? null)}
            className="block w-full text-sm"
          />
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Scanned PDFs may fail (OCR not supported yet).
          </p>
        </div>

        <div className="space-y-1">
          <label className="block text-sm font-medium">
            Text minutes (optional)
          </label>
          <input
            type="file"
            accept="text/plain,.txt"
            onChange={(e) => setText(e.target.files?.[0] ?? null)}
            className="block w-full text-sm"
          />
        </div>

        {error ? (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900/40 dark:bg-red-950/40 dark:text-red-200">
            {error}
          </div>
        ) : null}

        <button
          type="submit"
          disabled={!canSubmit}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
        >
          {submitting ? "Importing…" : "Upload & import"}
        </button>
      </form>
    </main>
  );
}
