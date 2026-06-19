from __future__ import annotations

import argparse
import sys
from pathlib import Path

from advisors.cache import CacheStore, fetch_entries
from advisors.coverage import seed_coverage_rows, write_coverage_csv
from advisors.discover import (
    discover_faculty_lists_from_cache,
    discover_tsinghua_faculty_lists_from_cache,
    discover_tsinghua_profiles_from_cache,
    discover_tsinghua_units_from_cache,
    discover_profiles_from_cache,
    discover_units_from_cache,
    write_discovered_sources_yaml,
)
from advisors.extract import extract_profile_text
from advisors.parquet import write_dataset_tables, write_source_pages
from advisors.registry import load_registry
from advisors.url_utils import normalize_url
from advisors.release import build_manifest, write_manifest
from advisors.xjtu_portal import discover_xjtu_profiles_from_portal

PROFILE_SOURCE_TYPES = {"profile", "teacher_profile", "faculty_profile", "profile_page"}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="advisors")
    subparsers = parser.add_subparsers(required=True)

    validate = subparsers.add_parser("validate-registry")
    validate.add_argument("--sources", default="configs/sources.yaml")
    validate.set_defaults(func=_validate_registry)

    coverage = subparsers.add_parser("seed-coverage")
    coverage.add_argument("--sources", default="configs/sources.yaml")
    coverage.add_argument("--out", default="data/working/coverage.csv")
    coverage.set_defaults(func=_seed_coverage)

    cache = subparsers.add_parser("cache-sources")
    cache.add_argument("--sources", default="configs/sources.yaml")
    cache.add_argument("--university", default=None)
    cache.add_argument("--cache-root", default=None)
    cache.add_argument("--out", default=None)
    cache.add_argument("--limit", type=int, default=None)
    cache.add_argument("--delay-seconds", type=float, default=1.0)
    cache.add_argument("--timeout-seconds", type=float, default=20.0)
    cache.add_argument("--ignore-robots", action="store_true")
    cache.add_argument("--continue-on-error", action="store_true")
    cache.set_defaults(func=_cache_sources)

    discover = subparsers.add_parser("discover-tsinghua-profiles")
    discover.add_argument("--cache-root", default="data/cache/thu")
    discover.add_argument("--out", default="data/working/thu/thu_discovered_profiles.yaml")
    discover.set_defaults(func=_discover_tsinghua_profiles)

    discover_units = subparsers.add_parser("discover-tsinghua-units")
    discover_units.add_argument("--cache-root", default="data/cache/thu")
    discover_units.add_argument("--out", default="data/working/thu/thu_discovered_units.yaml")
    discover_units.set_defaults(func=_discover_tsinghua_units)

    discover_faculty_lists = subparsers.add_parser("discover-tsinghua-faculty-lists")
    discover_faculty_lists.add_argument("--cache-root", default="data/cache/thu")
    discover_faculty_lists.add_argument(
        "--out",
        default="data/working/thu/thu_discovered_faculty_lists.yaml",
    )
    discover_faculty_lists.set_defaults(func=_discover_tsinghua_faculty_lists)

    generic_units = subparsers.add_parser("discover-units")
    generic_units.add_argument("--sources", required=True)
    generic_units.add_argument("--university", required=True)
    generic_units.add_argument("--cache-root", default=None)
    generic_units.add_argument("--out", required=True)
    generic_units.set_defaults(func=_discover_units)

    generic_faculty_lists = subparsers.add_parser("discover-faculty-lists")
    generic_faculty_lists.add_argument("--sources", required=True)
    generic_faculty_lists.add_argument("--university", required=True)
    generic_faculty_lists.add_argument("--cache-root", default=None)
    generic_faculty_lists.add_argument("--out", required=True)
    generic_faculty_lists.set_defaults(func=_discover_faculty_lists)

    generic_profiles = subparsers.add_parser("discover-profiles")
    generic_profiles.add_argument("--sources", required=True)
    generic_profiles.add_argument("--university", required=True)
    generic_profiles.add_argument("--cache-root", default=None)
    generic_profiles.add_argument("--out", required=True)
    generic_profiles.set_defaults(func=_discover_profiles)

    xjtu_portal = subparsers.add_parser("discover-xjtu-portal-profiles")
    xjtu_portal.add_argument("--cache-root", default="data/cache/xjtu")
    xjtu_portal.add_argument("--out", required=True)
    xjtu_portal.add_argument("--source-pages-out", default=None)
    xjtu_portal.add_argument("--pagesize", type=int, default=100)
    xjtu_portal.add_argument("--delay-seconds", type=float, default=0.2)
    xjtu_portal.add_argument("--timeout-seconds", type=float, default=20.0)
    xjtu_portal.add_argument("--limit-pages", type=int, default=None)
    xjtu_portal.set_defaults(func=_discover_xjtu_portal_profiles)

    extract = subparsers.add_parser("extract-cache")
    extract.add_argument("--cache-root", default=None)
    extract.add_argument("--out-dir", default=None)
    extract.add_argument(
        "--sources",
        action="append",
        default=[],
        help="Optional source registries used to provide name hints for cached profile pages.",
    )
    extract.add_argument("--limit", type=int, default=None)
    extract.add_argument(
        "--include-non-profile",
        action="store_true",
        help="Extract every cached page. By default only teacher profile source types are extracted.",
    )
    extract.set_defaults(func=_extract_cache)

    manifest = subparsers.add_parser("write-manifest")
    manifest.add_argument("--release-dir", required=True)
    manifest.add_argument("--dataset-version", required=True)
    manifest.add_argument("--schema-version", default="0.1.0")
    manifest.add_argument("--university", action="append", default=[])
    manifest.add_argument("--out", default=None)
    manifest.add_argument("--cache-batch-id", default=None)
    manifest.add_argument("--coverage-report-path", default=None)
    manifest.add_argument("--quality-report-path", default=None)
    manifest.add_argument("--license", default=None)
    manifest.add_argument("--notes", default=None)
    manifest.set_defaults(func=_write_manifest)

    return parser


def _validate_registry(args: argparse.Namespace) -> int:
    registry = load_registry(args.sources)
    errors = registry.validate()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"Registry OK: {len(registry.universities)} universities, {len(registry.entries)} entries")
    return 0


def _seed_coverage(args: argparse.Namespace) -> int:
    registry = load_registry(args.sources)
    rows = seed_coverage_rows(list(registry.entries))
    write_coverage_csv(rows, args.out)
    print(f"Wrote {len(rows)} coverage rows to {args.out}")
    return 0


def _cache_sources(args: argparse.Namespace) -> int:
    registry = load_registry(args.sources)
    errors = registry.validate()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    entries = list(registry.entries)
    if args.university:
        entries = [entry for entry in entries if entry.university_id == args.university]
    if args.limit is not None:
        entries = entries[: args.limit]

    cache_root = _cache_root(args.cache_root, args.university)
    if args.continue_on_error:
        records = _fetch_entries_continue_on_error(args, entries)
    else:
        records = fetch_entries(
            entries,
            CacheStore(cache_root),
            timeout_seconds=args.timeout_seconds,
            delay_seconds=args.delay_seconds,
            respect_robots=not args.ignore_robots,
        )
    out = args.out or _working_path("source_pages.parquet", args.university)
    write_source_pages((record.source_page_row() for record in records), out)
    print(f"Cached {len(records)} source pages and wrote {out}")
    return 0


def _fetch_entries_continue_on_error(
    args: argparse.Namespace,
    entries,
):
    import time

    from advisors.cache import RobotsPolicy, fetch_source_entry

    records = []
    errors = 0
    store = CacheStore(_cache_root(args.cache_root, args.university))
    robots_policy = RobotsPolicy("AdvisorsDataBot/0.1 (+https://github.com/open-data; research dataset)")
    for index, entry in enumerate(entries):
        if index and args.delay_seconds > 0:
            time.sleep(args.delay_seconds)
        try:
            records.append(
                fetch_source_entry(
                    entry,
                    store,
                    timeout_seconds=args.timeout_seconds,
                    respect_robots=not args.ignore_robots,
                    robots_policy=robots_policy,
                )
            )
        except Exception as exc:  # noqa: BLE001 - CLI should keep a long crawl moving.
            errors += 1
            print(f"Fetch failed for {entry.id} {entry.url}: {exc}", file=sys.stderr)
    if errors:
        print(f"Finished with {errors} fetch errors.", file=sys.stderr)
    return records


def _discover_tsinghua_profiles(args: argparse.Namespace) -> int:
    sources = discover_tsinghua_profiles_from_cache(args.cache_root)
    write_discovered_sources_yaml(sources, args.out)
    print(f"Discovered {len(sources)} Tsinghua teacher profile candidates and wrote {args.out}")
    return 0


def _discover_tsinghua_units(args: argparse.Namespace) -> int:
    sources = discover_tsinghua_units_from_cache(args.cache_root)
    write_discovered_sources_yaml(sources, args.out)
    print(f"Discovered {len(sources)} Tsinghua unit candidates and wrote {args.out}")
    return 0


def _discover_tsinghua_faculty_lists(args: argparse.Namespace) -> int:
    sources = discover_tsinghua_faculty_lists_from_cache(args.cache_root)
    write_discovered_sources_yaml(sources, args.out)
    print(f"Discovered {len(sources)} Tsinghua faculty list candidates and wrote {args.out}")
    return 0


def _discover_units(args: argparse.Namespace) -> int:
    university = _get_university(args.sources, args.university)
    sources = discover_units_from_cache(
        _cache_root(args.cache_root, args.university),
        university_name_zh=university.name_zh,
        source_id_prefix=f"{university.id}-unit",
        allowed_domains=list(university.allowed_domains),
    )
    write_discovered_sources_yaml(
        sources,
        args.out,
        university_id=university.id,
        university_name_zh=university.name_zh,
        university_name_en=university.name_en,
        allowed_domains=list(university.allowed_domains),
    )
    print(f"Discovered {len(sources)} {university.name_zh} unit candidates and wrote {args.out}")
    return 0


def _discover_faculty_lists(args: argparse.Namespace) -> int:
    university = _get_university(args.sources, args.university)
    sources = discover_faculty_lists_from_cache(
        _cache_root(args.cache_root, args.university),
        university_name_zh=university.name_zh,
        source_id_prefix=f"{university.id}-faculty-list",
        allowed_domains=list(university.allowed_domains),
    )
    write_discovered_sources_yaml(
        sources,
        args.out,
        university_id=university.id,
        university_name_zh=university.name_zh,
        university_name_en=university.name_en,
        allowed_domains=list(university.allowed_domains),
    )
    print(
        f"Discovered {len(sources)} {university.name_zh} faculty list candidates and wrote {args.out}"
    )
    return 0


def _discover_profiles(args: argparse.Namespace) -> int:
    university = _get_university(args.sources, args.university)
    sources = discover_profiles_from_cache(
        _cache_root(args.cache_root, args.university),
        university_name_zh=university.name_zh,
        source_id_prefix=f"{university.id}-profile",
        allowed_domains=list(university.allowed_domains),
    )
    write_discovered_sources_yaml(
        sources,
        args.out,
        university_id=university.id,
        university_name_zh=university.name_zh,
        university_name_en=university.name_en,
        allowed_domains=list(university.allowed_domains),
    )
    print(
        f"Discovered {len(sources)} {university.name_zh} teacher profile candidates and wrote {args.out}"
    )
    return 0


def _discover_xjtu_portal_profiles(args: argparse.Namespace) -> int:
    result = discover_xjtu_profiles_from_portal(
        cache_root=args.cache_root,
        out=args.out,
        source_pages_out=args.source_pages_out,
        pagesize=args.pagesize,
        delay_seconds=args.delay_seconds,
        timeout_seconds=args.timeout_seconds,
        limit_pages=args.limit_pages,
    )
    print(
        "Discovered "
        f"{len(result.sources)} XJTU teacher profile candidates from portal API "
        f"({len(result.source_page_rows)} index pages, totalnum={result.totalnum}, "
        f"totalpage={result.totalpage}) and wrote {args.out}"
    )
    return 0


def _get_university(sources_path: str, university_id: str):
    registry = load_registry(sources_path)
    for university in registry.universities:
        if university.id == university_id:
            return university
    raise SystemExit(f"University {university_id!r} not found in {sources_path}")


def _cache_root(cache_root: str | None, university_id: str | None = None) -> str:
    if cache_root:
        return cache_root
    if university_id:
        return f"data/cache/{university_id}"
    return "data/cache"


def _single_university_id_from_sources(paths: list[str]) -> str | None:
    university_ids: set[str] = set()
    for path in paths:
        registry = load_registry(path)
        university_ids.update(university.id for university in registry.universities)
    if len(university_ids) == 1:
        return next(iter(university_ids))
    return None


def _cache_root_from_sources(cache_root: str | None, source_paths: list[str]) -> str:
    if cache_root:
        return cache_root
    return _cache_root(None, _single_university_id_from_sources(source_paths))


def _working_path(name: str, university_id: str | None = None) -> str:
    if university_id:
        return f"data/working/{university_id}/{name}"
    return f"data/working/{name}"


def _extract_cache(args: argparse.Namespace) -> int:
    university_id = _single_university_id_from_sources(args.sources)
    store = CacheStore(_cache_root_from_sources(args.cache_root, args.sources))
    name_hints = _load_name_hints(args.sources)
    source_ids, source_urls = _load_source_filters(args.sources)
    tables: dict[str, list[dict[str, object]]] = {
        "teachers": [],
        "teacher_names": [],
        "teacher_attributes": [],
        "teacher_sections": [],
    }
    records = list(store.iter_records())
    if args.limit is not None:
        records = records[: args.limit]

    skipped = 0
    for record in records:
        if source_ids or source_urls:
            if record.source_id not in source_ids and normalize_url(record.source_url) not in source_urls:
                skipped += 1
                continue
        if not args.include_non_profile and record.source_type not in PROFILE_SOURCE_TYPES:
            skipped += 1
            continue
        if not (200 <= record.status_code < 300):
            skipped += 1
            continue
        if not record.text_cache_path:
            continue
        text_path = Path(record.text_cache_path)
        if not text_path.exists():
            continue
        extracted = extract_profile_text(
            profile_id=record.cache_key,
            person_id=None,
            source_url=record.source_url,
            university=record.university,
            department=record.department,
            homepage_url=record.source_url,
            fetched_at=record.fetched_at,
            name=record.name_hint or name_hints.get(record.source_id) or name_hints.get(record.source_url),
            text=text_path.read_text(encoding="utf-8"),
        )
        for table_name, rows in extracted.items():
            if table_name in tables:
                tables[table_name].extend(rows)

    out_dir = args.out_dir or _working_path("extracted", university_id)
    write_dataset_tables(tables, out_dir)
    print(
        "Extracted "
        f"{len(tables['teachers'])} profiles from cache and wrote Parquet tables to {out_dir} "
        f"(skipped {skipped} non-profile pages)"
    )
    return 0


def _load_name_hints(paths: list[str]) -> dict[str, str]:
    hints: dict[str, str] = {}
    for path in paths:
        registry = load_registry(path)
        for entry in registry.entries:
            if entry.name_hint:
                hints[entry.id] = entry.name_hint
                hints[entry.normalized_url] = entry.name_hint
    return hints


def _load_source_filters(paths: list[str]) -> tuple[set[str], set[str]]:
    source_ids: set[str] = set()
    source_urls: set[str] = set()
    for path in paths:
        registry = load_registry(path)
        for entry in registry.entries:
            source_ids.add(entry.id)
            source_urls.add(entry.normalized_url)
    return source_ids, source_urls


def _write_manifest(args: argparse.Namespace) -> int:
    release_dir = Path(args.release_dir)
    manifest = build_manifest(
        release_dir=release_dir,
        dataset_version=args.dataset_version,
        schema_version=args.schema_version,
        universities=sorted(args.university),
        cache_batch_id=args.cache_batch_id,
        coverage_report_path=args.coverage_report_path,
        quality_report_path=args.quality_report_path,
        license_name=args.license,
        notes=args.notes,
    )
    out = args.out or release_dir / "manifest.json"
    write_manifest(manifest, out)
    print(f"Wrote manifest to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
