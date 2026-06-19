from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from advisors.registry import SourceEntry


@dataclass(frozen=True)
class CoverageRow:
    university: str
    school_or_department: str | None
    source_entry_url: str
    source_entry_type: str
    allowed_domain: str
    discovered_list_pages: int
    visited_list_pages: int
    discovered_profile_pages: int
    cached_profile_pages: int
    parsed_profile_pages: int
    failed_pages: int
    failure_reason: str | None
    reviewed_at: str | None


def seed_coverage_rows(entries: list[SourceEntry]) -> list[CoverageRow]:
    rows: list[CoverageRow] = []
    for entry in entries:
        rows.append(
            CoverageRow(
                university=entry.university_name_zh,
                school_or_department=entry.department,
                source_entry_url=entry.normalized_url,
                source_entry_type=entry.type,
                allowed_domain=", ".join(entry.allowed_domains),
                discovered_list_pages=1 if "list" in entry.type or "portal" in entry.type else 0,
                visited_list_pages=0,
                discovered_profile_pages=0,
                cached_profile_pages=0,
                parsed_profile_pages=0,
                failed_pages=0,
                failure_reason=None,
                reviewed_at=None,
            )
        )
    return rows


def write_coverage_csv(rows: list[CoverageRow], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CoverageRow.__dataclass_fields__))
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)
