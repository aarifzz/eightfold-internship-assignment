"""Skill canonicalization and deduplication."""

from __future__ import annotations

import re
from typing import Iterable

DEFAULT_SKILL_SYNONYMS: dict[str, str] = {
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "py": "Python",
    "python3": "Python",
    "python 3": "Python",
    "golang": "Go",
    "go lang": "Go",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "reactjs": "React",
    "react.js": "React",
    "aws": "AWS",
    "amazon web services": "AWS",
    "ml": "Machine Learning",
    "machine-learning": "Machine Learning",
    "ai": "Artificial Intelligence",
    "c sharp": "C#",
    "c#": "C#",
    "cpp": "C++",
    "c plus plus": "C++",
}


def _canonical_key(skill: str) -> str:
    return re.sub(r"[^a-z0-9+#]+", "", skill.lower())


def canonicalize_skill(skill: str, synonyms: dict[str, str] | None = None) -> str:
    cleaned = skill.strip()
    if not cleaned:
        return cleaned
    lookup = {**DEFAULT_SKILL_SYNONYMS, **(synonyms or {})}
    lowered = cleaned.lower()
    if lowered in lookup:
        return lookup[lowered]
    key = _canonical_key(cleaned)
    for alias, canonical in lookup.items():
        if _canonical_key(alias) == key:
            return canonical
    # Title-case short tokens; preserve known acronyms/casing for multi-word skills.
    if " " in cleaned or len(cleaned) > 4:
        return cleaned.title() if cleaned.islower() else cleaned
    return cleaned.upper() if cleaned.isupper() else cleaned.title()


def canonicalize_skills(
    skills: Iterable[str],
    *,
    synonyms: dict[str, str] | None = None,
) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for skill in skills:
        canonical = canonicalize_skill(skill, synonyms)
        if not canonical:
            continue
        key = _canonical_key(canonical)
        if key in seen:
            continue
        seen.add(key)
        result.append(canonical)
    return sorted(result, key=lambda item: item.lower())
