from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def normalize_url(url: str) -> str:
    """Return a stable URL representation for cache keys and source matching."""
    split = urlsplit(url.strip())
    scheme = split.scheme.lower() or "https"
    netloc = split.netloc.lower()
    path = split.path or "/"
    query = urlencode(sorted(parse_qsl(split.query, keep_blank_values=True)), doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def cache_key_for_url(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()


def host_matches(host: str, patterns: list[str]) -> bool:
    host = host.lower().strip(".")
    for pattern in patterns:
        pattern = pattern.lower().strip()
        if pattern.startswith("*."):
            suffix = pattern[2:].strip(".")
            if host == suffix or host.endswith(f".{suffix}"):
                return True
        elif host == pattern.strip("."):
            return True
    return False


def host_from_url(url: str) -> str:
    return urlsplit(url).hostname or ""
