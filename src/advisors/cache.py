from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator, Mapping
from urllib import robotparser
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from advisors.registry import SourceEntry
from advisors.url_utils import cache_key_for_url, host_from_url, normalize_url

DEFAULT_USER_AGENT = "AdvisorsDataBot/0.1 (+https://github.com/open-data; research dataset)"


@dataclass(frozen=True)
class CacheRecord:
    source_url: str
    final_url: str
    university: str
    department: str | None
    fetched_at: str
    status_code: int
    cache_key: str
    cache_path: str
    text_cache_path: str | None
    content_hash: str
    text_hash: str | None
    content_type: str | None
    encoding: str | None
    response_headers: dict[str, str]
    parser_name: str
    parser_version: str
    source_id: str | None = None
    source_type: str = "unknown"
    name_hint: str | None = None

    def source_page_row(self) -> dict[str, object]:
        return {
            "source_url": self.source_url,
            "university": self.university,
            "department": self.department,
            "fetched_at": self.fetched_at,
            "status_code": self.status_code,
            "cache_key": self.cache_key,
            "cache_path": self.cache_path,
            "content_hash": self.content_hash,
            "text_hash": self.text_hash,
            "parser_name": self.parser_name,
            "parser_version": self.parser_version,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "name_hint": self.name_hint,
        }


class CacheStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.pages_dir = self.root / "pages"
        self.text_dir = self.root / "text"
        self.meta_dir = self.root / "metadata"

    def write_page(
        self,
        *,
        source_url: str,
        final_url: str,
        university: str,
        department: str | None,
        status_code: int,
        content: bytes,
        headers: Mapping[str, str],
        encoding: str | None,
        parser_name: str = "cache.fetch",
        parser_version: str = "0.1.0",
        source_id: str | None = None,
        source_type: str = "profile",
        name_hint: str | None = None,
        fetched_at: datetime | None = None,
    ) -> CacheRecord:
        normalized_url = normalize_url(source_url)
        key = cache_key_for_url(normalized_url)
        fetched_at = fetched_at or datetime.now(UTC)
        fetched_at_text = fetched_at.isoformat()
        content_hash = hashlib.sha256(content).hexdigest()
        content_type = headers.get("content-type") or headers.get("Content-Type")

        page_path = self._path_for(self.pages_dir, key, _suffix_for_content_type(content_type))
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_bytes(content)

        text = _html_to_text(content, encoding) if _is_html(content_type) else None
        text_path: Path | None = None
        text_hash: str | None = None
        if text:
            text_path = self._path_for(self.text_dir, key, ".txt")
            text_path.parent.mkdir(parents=True, exist_ok=True)
            text_path.write_text(text, encoding="utf-8")
            text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        record = CacheRecord(
            source_url=normalized_url,
            final_url=normalize_url(final_url),
            university=university,
            department=department,
            fetched_at=fetched_at_text,
            status_code=status_code,
            cache_key=key,
            cache_path=str(page_path),
            text_cache_path=str(text_path) if text_path else None,
            content_hash=content_hash,
            text_hash=text_hash,
            content_type=content_type,
            encoding=encoding,
            response_headers=_header_summary(headers),
            parser_name=parser_name,
            parser_version=parser_version,
            source_id=source_id,
            source_type=source_type,
            name_hint=name_hint,
        )

        meta_path = self._path_for(self.meta_dir, key, ".json")
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(
            json.dumps(asdict(record), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return record

    @staticmethod
    def _path_for(root: Path, key: str, suffix: str) -> Path:
        return root / key[:2] / key[2:4] / f"{key}{suffix}"

    def iter_records(self) -> Iterator[CacheRecord]:
        for path in sorted(self.meta_dir.glob("*/*/*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            yield CacheRecord(**data)


class RobotsPolicy:
    def __init__(self, user_agent: str):
        self.user_agent = user_agent
        self._parsers: dict[str, robotparser.RobotFileParser] = {}

    def can_fetch(self, url: str) -> bool:
        split = urlsplit(url)
        base = f"{split.scheme}://{split.netloc}"
        parser = self._parsers.get(base)
        if parser is None:
            parser = robotparser.RobotFileParser(urljoin(base, "/robots.txt"))
            try:
                parser.read()
            except OSError:
                return True
            self._parsers[base] = parser
        return parser.can_fetch(self.user_agent, url)


def fetch_source_entry(
    entry: SourceEntry,
    store: CacheStore,
    *,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout_seconds: float = 20,
    respect_robots: bool = True,
    robots_policy: RobotsPolicy | None = None,
) -> CacheRecord:
    if not entry.is_allowed():
        raise ValueError(f"Refusing to fetch URL outside allowed domains: {entry.url}")

    normalized_url = entry.normalized_url
    if respect_robots:
        robots_policy = robots_policy or RobotsPolicy(user_agent)
        if not robots_policy.can_fetch(normalized_url):
            raise PermissionError(f"robots.txt disallows fetching: {normalized_url}")

    with httpx.Client(
        follow_redirects=True,
        timeout=timeout_seconds,
        headers={"User-Agent": user_agent},
    ) as client:
        response = client.get(normalized_url)

    return store.write_page(
        source_url=normalized_url,
        final_url=str(response.url),
        university=entry.university_name_zh,
        department=entry.department,
        status_code=response.status_code,
        content=response.content,
        headers=response.headers,
        encoding=response.encoding,
        source_id=entry.id,
        source_type=entry.type,
        name_hint=entry.name_hint,
    )


def fetch_entries(
    entries: list[SourceEntry],
    store: CacheStore,
    *,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout_seconds: float = 20,
    delay_seconds: float = 1,
    respect_robots: bool = True,
) -> list[CacheRecord]:
    records: list[CacheRecord] = []
    robots_policy = RobotsPolicy(user_agent)
    for index, entry in enumerate(entries):
        if index and delay_seconds > 0:
            time.sleep(delay_seconds)
        records.append(
            fetch_source_entry(
                entry,
                store,
                user_agent=user_agent,
                timeout_seconds=timeout_seconds,
                respect_robots=respect_robots,
                robots_policy=robots_policy,
            )
        )
    return records


def _is_html(content_type: str | None) -> bool:
    if not content_type:
        return True
    return "html" in content_type.lower()


def _suffix_for_content_type(content_type: str | None) -> str:
    if _is_html(content_type):
        return ".html"
    if content_type and "json" in content_type.lower():
        return ".json"
    return ".bin"


def _html_to_text(content: bytes, encoding: str | None) -> str:
    text = content.decode(encoding or "utf-8", errors="replace")
    soup = BeautifulSoup(text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    lines = [line.strip() for line in soup.get_text("\n").splitlines()]
    return "\n".join(line for line in lines if line)


def _header_summary(headers: Mapping[str, str]) -> dict[str, str]:
    keep = {"content-type", "last-modified", "etag", "cache-control"}
    return {key.lower(): value for key, value in headers.items() if key.lower() in keep}
