"""Draft auditing — thin adapter over the installed skill's audit script.

The analysis itself lives in the skill bundle
(`skills/<skill>/scripts/audit_draft.py`) so the bundle stays self-contained
and usable as a standalone CLI. This module just locates it, imports it once,
and re-exports `audit_text`.

Returns a plain dict, so the web layer can hand it straight to JSONResponse.
"""
from __future__ import annotations

import importlib.util
from functools import lru_cache
from pathlib import Path

from .loader import DEFAULT_SKILL, skill_dir


class AuditUnavailable(RuntimeError):
    """The installed skill has no audit script."""


@lru_cache(maxsize=8)
def _module(skill: str = DEFAULT_SKILL):
    path = skill_dir(skill) / "scripts" / "audit_draft.py"
    if not path.is_file():
        raise AuditUnavailable(f"no audit script in skill '{skill}'")
    spec = importlib.util.spec_from_file_location(f"_audit_{skill.replace('-', '_')}", path)
    if spec is None or spec.loader is None:
        raise AuditUnavailable(f"could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def available(skill: str = DEFAULT_SKILL) -> bool:
    try:
        _module(skill)
        return True
    except Exception:
        return False


def audit_text(text: str, section: str | None = None, skill: str = DEFAULT_SKILL) -> dict:
    """Audit a draft against the corpus register profile. See the skill's
    audit_draft.audit_text for the report shape."""
    return _module(skill).audit_text(text or "", section)
