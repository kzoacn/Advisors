from advisors.url_utils import cache_key_for_url, host_matches, normalize_url


def test_normalize_url_sorts_query_and_drops_fragment() -> None:
    assert normalize_url("HTTPS://Example.COM/path?b=2&a=1#frag") == (
        "https://example.com/path?a=1&b=2"
    )


def test_cache_key_uses_normalized_url() -> None:
    assert cache_key_for_url("https://example.com/path?b=2&a=1") == cache_key_for_url(
        "https://EXAMPLE.com/path?a=1&b=2#ignored"
    )


def test_host_matches_exact_and_wildcard_domains() -> None:
    assert host_matches("www.pku.edu.cn", ["*.pku.edu.cn"])
    assert host_matches("pku.edu.cn", ["*.pku.edu.cn"])
    assert host_matches("pku.edu.cn", ["pku.edu.cn"])
    assert not host_matches("example.com", ["*.pku.edu.cn"])
