from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import re

import yaml

from advisors.url_utils import host_from_url, host_matches, normalize_url


@dataclass(frozen=True)
class SourceEntry:
    id: str
    university_id: str
    university_name_zh: str
    university_name_en: str
    url: str
    type: str
    allowed_domains: tuple[str, ...]
    department: str | None = None
    status: str = "seed"
    notes: str | None = None
    name_hint: str | None = None

    @property
    def normalized_url(self) -> str:
        return normalize_url(self.url)

    def is_allowed(self) -> bool:
        return host_matches(host_from_url(self.normalized_url), list(self.allowed_domains))


@dataclass(frozen=True)
class UniversitySources:
    id: str
    name_zh: str
    name_en: str
    allowed_domains: tuple[str, ...]
    entries: tuple[SourceEntry, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SourceRegistry:
    version: int
    universities: tuple[UniversitySources, ...]

    @property
    def entries(self) -> tuple[SourceEntry, ...]:
        return tuple(entry for university in self.universities for entry in university.entries)

    def validate(self) -> list[str]:
        errors: list[str] = []
        seen_ids: set[str] = set()
        for university in self.universities:
            if not university.allowed_domains:
                errors.append(f"University {university.id} has no allowed_domains.")
            for entry in university.entries:
                if entry.id in seen_ids:
                    errors.append(f"Duplicate source entry id: {entry.id}.")
                seen_ids.add(entry.id)
                if not entry.url.startswith(("http://", "https://")):
                    errors.append(f"{entry.id} URL must be absolute: {entry.url}.")
                if not entry.is_allowed():
                    errors.append(
                        f"{entry.id} host is outside allowed domains: {entry.url} "
                        f"not in {list(entry.allowed_domains)}."
                    )
        return errors


def load_registry(path: str | Path) -> SourceRegistry:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return registry_from_dict(data)


def registry_from_dict(data: dict[str, Any]) -> SourceRegistry:
    universities: list[UniversitySources] = []
    for university_data in data.get("universities", []):
        allowed_domains = tuple(university_data.get("allowed_domains", []))
        entries = tuple(
            SourceEntry(
                id=entry["id"],
                university_id=university_data["id"],
                university_name_zh=university_data["name_zh"],
                university_name_en=university_data.get("name_en", ""),
                url=entry["url"],
                type=entry["type"],
                allowed_domains=allowed_domains,
                department=entry.get("department"),
                status=entry.get("status", "seed"),
                notes=entry.get("notes"),
                name_hint=entry.get("name_hint") or _name_hint_from_notes(entry.get("notes")),
            )
            for entry in university_data.get("entries", [])
        )
        universities.append(
            UniversitySources(
                id=university_data["id"],
                name_zh=university_data["name_zh"],
                name_en=university_data.get("name_en", ""),
                allowed_domains=allowed_domains,
                entries=entries,
            )
        )
    return SourceRegistry(version=int(data.get("version", 1)), universities=tuple(universities))


def _name_hint_from_notes(notes: str | None) -> str | None:
    if not notes:
        return None
    match = re.search(r"anchor='([^']+)'", notes)
    if match:
        value = match.group(1).strip()
        return value or None
    return None
