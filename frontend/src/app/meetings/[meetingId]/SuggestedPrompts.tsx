import React from "react";

type SuggestedPromptRenderItem = {
  promptId: string;
  prompt: string;
  answer: string;
  evidenceHref: string | null;
  evidenceCount: number;
};

type SuggestedPromptsProps = {
  prompts: SuggestedPromptRenderItem[];
};

export function SuggestedPrompts({ prompts }: SuggestedPromptsProps) {
  if (prompts.length === 0) {
    return null;
  }

  return (
    <section
      aria-label="Suggested follow-up prompts"
      className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-lg shadow-slate-200/60"
    >
      <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
        Suggested follow-up prompts
      </h2>
      <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-600">
        Quick answers to a fixed set of common follow-up questions from this
        meeting record.
      </p>
      <ol className="mt-6 space-y-4">
        {prompts.map((prompt) => (
          <li
            key={prompt.promptId}
            className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 shadow-sm"
          >
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Approved prompt
            </p>
            <p className="mt-2 text-base font-semibold tracking-tight text-slate-950">
              {prompt.prompt}
            </p>
            <p className="mt-4 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Answer
            </p>
            <p className="mt-2 text-sm leading-7 text-slate-700">
              {prompt.answer}
            </p>
            {prompt.evidenceHref ? (
              <div className="mt-4 flex flex-wrap gap-3">
                <a
                  href={prompt.evidenceHref}
                  aria-label={`View evidence for ${prompt.prompt}`}
                  className="inline-flex items-center rounded-full border border-cyan-200 bg-cyan-50 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-800 transition hover:border-cyan-300 hover:bg-cyan-100"
                >
                  View evidence
                </a>
                <span className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">
                  {prompt.evidenceCount} source{" "}
                  {prompt.evidenceCount === 1 ? "excerpt" : "excerpts"}
                </span>
              </div>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
