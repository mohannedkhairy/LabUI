"""
Citation-enforced prompt builder for Ollama chat API.
Supports per-agent system prompts via generation.agents.
Supports doc_context for uploaded PDF/document text.

Skill-backed agents (currently `writing`) take two extra arguments:
    section  — which manuscript section is being written ("results", "intro", …)
    mode     — "draft" (new prose) or "revise" (reworking an existing draft)
Both are passed to generation.agents.resolve_system(), which assembles the
matching slice of the installed skill pack. See Local_Rag/rag/skills/loader.py.
"""
from generation.agents import get_agent, resolve_system, AGENTS, DEFAULT_AGENT
from generation.citations import build_citation_map


def build_user_prompt(
    query: str,
    chunks: list[dict],
    agent_id: str = DEFAULT_AGENT,
    web_results: list[dict] | None = None,
    doc_context: str | None = None,
    memories: list[dict] | None = None,
    style_samples: str | None = None,
    draft_text: str | None = None,
    section: str | None = None,
    mode: str = "draft",
) -> str:
    agent = get_agent(agent_id)

    # ── Local paper excerpts ──────────────────────────────────────────────────
    # One citation number per paper, shared with the source panel and the
    # auto-appended References list (see generation.citations).
    cite_map = build_citation_map(chunks)
    excerpt_lines = []
    for c in chunks:
        n = cite_map.get(c["paper_id"], "?")
        block = (
            f"---\n"
            f"[{n}] {c.get('title', '')}\n"
            f"Section: {c.get('section_name', '')} "
            f"(pages {c.get('page_start', '?')}-{c.get('page_end', '?')})\n"
            f"{c['text']}\n"
            f"---"
        )
        excerpt_lines.append(block)

    excerpts = "\n\n".join(excerpt_lines) if excerpt_lines else "(no local papers retrieved)"

    # ── Web search results ────────────────────────────────────────────────────
    web_section = ""
    if web_results:
        web_lines = []
        for r in web_results:
            web_lines.append(
                f"[web:{r['index']}] {r['title']}\n"
                f"URL: {r['url']}\n"
                f"{r['snippet']}"
            )
        web_section = (
            "\n\n# Web search results (supplementary — cite as [web:N])\n"
            + "\n\n".join(web_lines)
        )

    # ── Uploaded document context ─────────────────────────────────────────────
    doc_section = ""
    if doc_context:
        doc_section = f"\n\n# Attached document (user-uploaded)\n{doc_context}"

    # ── Long-term memory context ──────────────────────────────────────────────
    memory_section = ""
    if memories:
        mem_lines = "\n".join(f"- {m['content']}" for m in memories)
        memory_section = (
            "\n\n# Research memory (findings from past conversations — use as background context)\n"
            + mem_lines
        )

    # ── Writing-style samples (writing agent) ─────────────────────────────────
    style_section = ""
    if style_samples:
        style_section = (
            "\n\n# Writing style samples (the user's own prose — match this voice, "
            "rhythm, and vocabulary)\n"
            + style_samples
        )

    # ── Existing draft being revised (writing agent, revise mode) ─────────────
    draft_section = ""
    if draft_text:
        draft_section = (
            "\n\n# Current draft (revise THIS text; keep its facts, numbers, and "
            "citations exactly as they are)\n" + draft_text
        )

    instruction = agent.get("instruction", "")
    if section:
        instruction += (
            f" This passage belongs to the {section.upper()} section — follow that "
            "section's corpus anchors in the writing standard (citation density, "
            "passive rate, hedging rate, sentence length)."
        )
    if mode == "revise" and draft_text:
        instruction += (
            " Return the revised passage only. Do not add findings, numbers, or "
            "citations that are not already in the draft or the excerpts; if a "
            "sentence is unsupported, keep it and flag it in the notes line "
            "instead of deleting it."
        )
    if web_results:
        instruction += (
            " You may also cite web search results as [web:N] where N is the result number. "
            "Prefer local paper excerpts over web results when both are available."
        )
    if doc_context:
        instruction += (
            " The user has also attached a document whose full text is provided above. "
            "You may reference it directly in your answer."
        )

    return (
        f"# Input\n{query}\n\n"
        f"# Local paper excerpts\n{excerpts}"
        f"{web_section}"
        f"{doc_section}"
        f"{memory_section}"
        f"{style_section}"
        f"{draft_section}\n\n"
        f"# Instructions\n{instruction}"
    )


def build_messages(
    query: str,
    chunks: list[dict],
    agent_id: str = DEFAULT_AGENT,
    web_results: list[dict] | None = None,
    doc_context: str | None = None,
    memories: list[dict] | None = None,
    style_samples: str | None = None,
    draft_text: str | None = None,
    section: str | None = None,
    mode: str = "draft",
) -> list[dict]:
    return [
        {"role": "system", "content": resolve_system(agent_id, section=section, mode=mode)},
        {"role": "user",   "content": build_user_prompt(
            query, chunks, agent_id, web_results, doc_context, memories,
            style_samples, draft_text, section, mode,
        )},
    ]
