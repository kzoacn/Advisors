from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


@dataclass(frozen=True)
class ReleaseManifest:
    dataset_name: str
    dataset_version: str
    schema_version: str
    generated_at: str
    source_commit: str | None
    universities: list[str]
    release_files: list[str]
    row_counts: dict[str, int]
    source_page_count: int
    cache_batch_id: str | None
    parser_versions: dict[str, str]
    coverage_report_path: str | None
    quality_report_path: str | None
    license: str | None
    notes: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_manifest(
    *,
    release_dir: str | Path,
    dataset_version: str,
    schema_version: str,
    universities: list[str],
    cache_batch_id: str | None = None,
    parser_versions: dict[str, str] | None = None,
    coverage_report_path: str | None = None,
    quality_report_path: str | None = None,
    license_name: str | None = None,
    notes: str | None = None,
) -> ReleaseManifest:
    release_dir = Path(release_dir)
    parquet_files = sorted(release_dir.glob("*.parquet"))
    row_counts = {path.name: pq.read_metadata(path).num_rows for path in parquet_files}
    return ReleaseManifest(
        dataset_name="advisors",
        dataset_version=dataset_version,
        schema_version=schema_version,
        generated_at=datetime.now(UTC).isoformat(),
        source_commit=_git_commit(),
        universities=universities,
        release_files=[path.name for path in parquet_files],
        row_counts=row_counts,
        source_page_count=row_counts.get("source_pages.parquet", 0),
        cache_batch_id=cache_batch_id,
        parser_versions=parser_versions or {},
        coverage_report_path=coverage_report_path,
        quality_report_path=quality_report_path,
        license=license_name,
        notes=notes,
    )


def write_manifest(manifest: ReleaseManifest, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()
