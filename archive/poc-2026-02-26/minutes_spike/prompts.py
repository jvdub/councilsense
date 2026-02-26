from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:
    """Provenance identifier for a prompt template.

    Bump `version` whenever the prompt text changes in a way that could affect outputs.
    """

    id: str
    version: int


SUMMARIZE_AGENDA_ITEM_BULLETS = PromptTemplate(id="summarize_agenda_item.bullets", version=1)
SUMMARIZE_AGENDA_ITEM_TOON = PromptTemplate(id="summarize_agenda_item.toon", version=1)
SEMANTIC_CLASSIFY_RELEVANCE = PromptTemplate(id="pass_b.semantic_relevance", version=1)


def build_summarize_agenda_item_bullets_prompt(*, title: str, body_text: str) -> str:
    return (
        "You are helping summarize a city council agenda item for a resident.\n"
        "Return 3-8 concise bullet points, each on its own line.\n"
        "No preamble, no numbering required.\n\n"
        f"Title: {title.strip()}\n\n"
        "Body:\n"
        f"{body_text.strip()}\n"
    )


def build_summarize_agenda_item_toon_prompt(*, input_toon: str) -> str:
    return (
        "You are helping summarize a city council agenda item for a resident.\n"
        "You will be given meeting context as TOON-ish YAML.\n"
        "Return ONLY TOON-ish YAML with this exact schema (no extra keys):\n"
        "summary: [list of 2-5 concise bullet strings]\n"
        "actions: [optional list of action strings]\n"
        "entities: [optional list of entity strings]\n"
        "key_terms: [optional list of key term strings]\n"
        "citations: [list of 1-3 short direct quotes/snippets]\n\n"
        "INPUT_TOON:\n"
        f"{input_toon}\n"
    )


def build_semantic_relevance_prompt(
    *,
    category_id: str,
    category_description: str,
    category_keywords: list[str],
    candidate_kind: str,
    candidate_title: str,
    candidate_text: str,
    evidence_snippets: list[str],
) -> str:
    kws = ", ".join([k.strip() for k in category_keywords if isinstance(k, str) and k.strip()])
    ev = "\n".join([f"- {s.strip()}" for s in evidence_snippets if isinstance(s, str) and s.strip()])
    if not ev:
        ev = "- (none)"
    return (
        "You are a careful classifier for a resident's interest categories.\n"
        "Decide whether the CANDIDATE is truly relevant to the CATEGORY.\n"
        "Be strict about false positives (example: 'laundry room' is NOT a 'laundromat').\n\n"
        "Return ONLY valid JSON with this schema (no extra keys):\n"
        '{"relevant": true|false, "confidence": 0.0-1.0, "why": "...", "evidence": ["direct quote 1", "direct quote 2"]}\n'
        "Evidence must be 1-3 short direct quotes copied from the candidate text.\n\n"
        f"CATEGORY_ID: {category_id}\n"
        f"CATEGORY_DESCRIPTION: {category_description.strip()}\n"
        f"CATEGORY_KEYWORDS: {kws or '(none)'}\n\n"
        f"CANDIDATE_KIND: {candidate_kind}\n"
        f"CANDIDATE_TITLE: {candidate_title.strip()}\n\n"
        "EVIDENCE_SNIPPETS_FROM_PREFILTER:\n"
        f"{ev}\n\n"
        "CANDIDATE_TEXT:\n"
        f"{candidate_text.strip()}\n"
    )
