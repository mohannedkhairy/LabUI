"""Skill packs — markdown writing standards loaded progressively into prompts.

See loader.py for why nothing is ever loaded whole.
"""
from .loader import (                       # noqa: F401
    DEFAULT_SKILL,
    SECTION_MAP,
    SECTIONS,
    build_writing_brief,
    brief_stats,
    is_installed,
    list_skills,
    phrasebank_html,
)
