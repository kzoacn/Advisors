from datetime import UTC, datetime

from advisors.cache import CacheStore


def test_cache_store_writes_page_metadata_and_text(tmp_path) -> None:
    store = CacheStore(tmp_path)
    record = store.write_page(
        source_url="https://www.pku.edu.cn/teachers.html",
        final_url="https://www.pku.edu.cn/teachers.html",
        university="北京大学",
        department=None,
        status_code=200,
        content="<html><body><h1>教师</h1><script>skip()</script><p>邮箱 a@pku.edu.cn</p></body></html>".encode(),
        headers={"content-type": "text/html; charset=utf-8"},
        encoding="utf-8",
        source_id="pku-teachers",
        source_type="faculty_list",
        name_hint="教师入口",
        fetched_at=datetime(2026, 6, 18, tzinfo=UTC),
    )

    assert record.status_code == 200
    assert record.cache_path.endswith(".html")
    assert record.text_cache_path is not None
    assert record.source_id == "pku-teachers"
    assert record.source_type == "faculty_list"
    assert record.name_hint == "教师入口"
    assert "教师" in (tmp_path / "text" / record.cache_key[:2] / record.cache_key[2:4] / f"{record.cache_key}.txt").read_text(encoding="utf-8")
    assert record.source_page_row()["source_url"] == "https://www.pku.edu.cn/teachers.html"
    assert record.source_page_row()["source_type"] == "faculty_list"
