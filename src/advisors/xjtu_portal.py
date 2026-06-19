from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

from advisors.cache import CacheStore, DEFAULT_USER_AGENT
from advisors.discover import DiscoveredSource, write_discovered_sources_yaml
from advisors.parquet import write_source_pages
from advisors.url_utils import cache_key_for_url, host_matches, normalize_url


XJTU_PORTAL_URL = "https://gr.xjtu.edu.cn/"
XJTU_ADVANCE_SEARCH_URL = urljoin(XJTU_PORTAL_URL, "/system/resource/tsites/advancesearch.jsp")
XJTU_ALLOWED_DOMAINS = ["xjtu.edu.cn", "*.xjtu.edu.cn"]


@dataclass(frozen=True)
class XjtuPortalDiscoveryResult:
    sources: list[DiscoveredSource]
    source_page_rows: list[dict[str, object]]
    totalnum: int
    totalpage: int


def discover_xjtu_profiles_from_portal(
    *,
    cache_root: str | Path,
    out: str | Path,
    source_pages_out: str | Path | None = None,
    pagesize: int = 100,
    delay_seconds: float = 0.2,
    timeout_seconds: float = 20,
    limit_pages: int | None = None,
) -> XjtuPortalDiscoveryResult:
    """Fetch the official XJTU teacher-homepage portal index and write profile sources."""
    pagesize = min(max(pagesize, 1), 100)
    store = CacheStore(cache_root)
    options = _load_cached_portal_options(store) or {}
    base_params = _advance_search_params(options, pagesize=pagesize)
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Referer": XJTU_PORTAL_URL,
    }

    sources_by_url: dict[str, DiscoveredSource] = {}
    source_page_rows: list[dict[str, object]] = []
    totalnum = 0
    totalpage = 0

    with httpx.Client(follow_redirects=True, timeout=timeout_seconds, headers=headers) as client:
        page = 1
        while True:
            params = {**base_params, "pageindex": page}
            response = client.get(XJTU_ADVANCE_SEARCH_URL, params=params)
            record = store.write_page(
                source_url=str(response.url),
                final_url=str(response.url),
                university="西安交通大学",
                department=None,
                status_code=response.status_code,
                content=response.content,
                headers=response.headers,
                encoding=response.encoding or "utf-8",
                source_id=f"xjtu-teacher-index-api-page-{page:04d}",
                source_type="profile_index_api",
                fetched_at=datetime.now(UTC),
            )
            source_page_rows.append(record.source_page_row())

            data = response.json()
            totalnum = int(data.get("totalnum") or 0)
            totalpage = int(data.get("totalpage") or 0)
            for item in data.get("teacherData") or []:
                source = _source_from_teacher_item(item, discovered_from=str(response.url))
                if source and source.url not in sources_by_url:
                    sources_by_url[source.url] = source

            if page >= totalpage:
                break
            if limit_pages is not None and page >= limit_pages:
                break
            page += 1
            if delay_seconds > 0:
                time.sleep(delay_seconds)

    sources = sorted(sources_by_url.values(), key=lambda item: item.url)
    write_discovered_sources_yaml(
        sources,
        out,
        university_id="xjtu",
        university_name_zh="西安交通大学",
        university_name_en="Xi'an Jiaotong University",
        allowed_domains=XJTU_ALLOWED_DOMAINS,
    )
    if source_pages_out is not None:
        write_source_pages(source_page_rows, source_pages_out)

    return XjtuPortalDiscoveryResult(
        sources=sources,
        source_page_rows=source_page_rows,
        totalnum=totalnum,
        totalpage=totalpage,
    )


def parse_tsites_load_data_options(html: str) -> dict[str, object] | None:
    match = re.search(r"var\s+tsites_load_data_options\s*=\s*(\{.*?\})\s*;", html, re.S)
    if not match:
        return None
    return json.loads(match.group(1))


def _load_cached_portal_options(store: CacheStore) -> dict[str, object] | None:
    for record in store.iter_records():
        if record.source_url.rstrip("/") != XJTU_PORTAL_URL.rstrip("/"):
            continue
        if not record.cache_path:
            continue
        path = Path(record.cache_path)
        if not path.exists():
            continue
        html = path.read_text(encoding=record.encoding or "utf-8", errors="replace")
        return parse_tsites_load_data_options(html)
    return None


def _advance_search_params(options: dict[str, object], *, pagesize: int) -> dict[str, object]:
    return {
        "collegeid": 0,
        "disciplineid": 0,
        "enrollid": 0,
        "pageindex": 1,
        "pagesize": pagesize,
        "rankid": 0,
        "degreeid": 0,
        "honorid": 0,
        "py": "",
        "profilelen": options.get("profilelen", 1000),
        "teacherName": "",
        "searchDirection": "",
        "viewmode": options.get("viewMode", 8),
        "viewid": options.get("viewId", 1095185),
        "siteOwner": options.get("siteOwner", 2105667170),
        "viewUniqueId": options.get("viewUniqueId", 1095185),
        "showlang": options.get("showlang", "zh_CN"),
        "ispreview": str(options.get("ispreview", False)).lower(),
        "basenum": options.get("basenum", 0),
        "ellipsis": options.get("ellipsis", "..."),
        "alignright": options.get("alignright", "false"),
        "productType": options.get("productType", 0),
        "tutorType": "",
    }


def _source_from_teacher_item(
    item: dict[str, object],
    *,
    discovered_from: str,
) -> DiscoveredSource | None:
    raw_url = str(item.get("url") or "").strip()
    if not raw_url:
        return None
    url = normalize_url(urljoin(XJTU_PORTAL_URL, raw_url))
    host = urlsplit(url).hostname or ""
    if host in {"webvpn.xjtu.edu.cn", "ivpn.xjtu.edu.cn"}:
        return None
    if not host_matches(host, XJTU_ALLOWED_DOMAINS):
        return None
    name = _clean_text(item.get("name") or item.get("teacherName") or item.get("showName"))
    department = _clean_text(item.get("unit") or item.get("collegeName"))
    notes_parts = ["Discovered from XJTU teacher homepage portal API."]
    teacher_id = _clean_text(item.get("teacherId"))
    uid = _clean_text(item.get("uid"))
    if teacher_id:
        notes_parts.append(f"teacherId={teacher_id}")
    if uid:
        notes_parts.append(f"uid={uid}")
    return DiscoveredSource(
        id=_source_id(url),
        url=url,
        type="teacher_profile",
        department=department or None,
        status="discovered",
        notes="; ".join(notes_parts),
        discovered_from=discovered_from,
        anchor_text=name or "",
    )


def _source_id(url: str) -> str:
    normalized = normalize_url(url)
    split = re.sub(r"^https?://", "", normalized)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", split).strip("-").lower()
    digest = cache_key_for_url(normalized)[:8]
    return f"xjtu-profile-{slug[:72]}-{digest}"


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split())
