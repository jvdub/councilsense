import Link from "next/link";

export function TopNav() {
  return (
    <header className="border-b border-zinc-200 bg-white/70 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/60">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-3">
          <Link
            href="/meetings"
            className="text-sm font-semibold tracking-tight"
          >
            CouncilSense
          </Link>
          <span className="hidden text-xs text-zinc-500 dark:text-zinc-400 sm:inline">
            local-first
          </span>
        </div>

        <nav className="flex items-center gap-3 text-sm">
          <Link
            href="/meetings"
            className="rounded-md px-3 py-1.5 text-zinc-700 hover:bg-zinc-100 dark:text-zinc-200 dark:hover:bg-zinc-900"
          >
            Meetings
          </Link>
          <Link
            href="/upload"
            className="rounded-md bg-zinc-900 px-3 py-1.5 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
          >
            Upload
          </Link>
        </nav>
      </div>
    </header>
  );
}
