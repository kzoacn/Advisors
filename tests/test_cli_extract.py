from datetime import UTC, datetime

import pyarrow.parquet as pq

from advisors.cache import CacheStore
from advisors.cli import main


def test_extract_cache_cli_writes_structured_parquet_without_phone_numbers(tmp_path) -> None:
    cache_root = tmp_path / "cache"
    store = CacheStore(cache_root)
    store.write_page(
        source_url="https://www.pku.edu.cn/teacher/lisi",
        final_url="https://www.pku.edu.cn/teacher/lisi",
        university="北京大学",
        department="信息科学技术学院",
        status_code=200,
        content="""<html><body>
李四
职称：副教授
邮箱：li.si@pku.edu.cn
电话：010-62781234
研究方向：数据库
</body></html>""".encode(),
        headers={"content-type": "text/html; charset=utf-8"},
        encoding="utf-8",
        source_type="teacher_profile",
        fetched_at=datetime(2026, 6, 18, tzinfo=UTC),
    )

    out_dir = tmp_path / "out"
    assert main(["extract-cache", "--cache-root", str(cache_root), "--out-dir", str(out_dir)]) == 0

    teachers = pq.read_table(out_dir / "teachers.parquet").to_pylist()
    attributes = pq.read_table(out_dir / "teacher_attributes.parquet").to_pylist()
    flattened = f"{teachers}\n{attributes}"

    assert teachers[0]["name"] == "李四"
    assert "li.si@pku.edu.cn" in flattened
    assert "010-62781234" not in flattened
    assert "62781234" not in flattened


def test_extract_cache_cli_skips_non_profile_pages_by_default(tmp_path) -> None:
    cache_root = tmp_path / "cache"
    store = CacheStore(cache_root)
    store.write_page(
        source_url="https://www.cs.tsinghua.edu.cn/szzk/jzgml.htm",
        final_url="https://www.cs.tsinghua.edu.cn/szzk/jzgml.htm",
        university="清华大学",
        department="计算机科学与技术系",
        status_code=200,
        content="教师名录\n张三\n电话：010-62781234\n邮箱：zhangsan@tsinghua.edu.cn".encode(),
        headers={"content-type": "text/html; charset=utf-8"},
        encoding="utf-8",
        source_type="faculty_list",
        fetched_at=datetime(2026, 6, 18, tzinfo=UTC),
    )

    out_dir = tmp_path / "out"
    assert main(["extract-cache", "--cache-root", str(cache_root), "--out-dir", str(out_dir)]) == 0

    teachers = pq.read_table(out_dir / "teachers.parquet").to_pylist()
    assert teachers == []


def test_extract_cache_cli_sources_limit_cached_profiles(tmp_path) -> None:
    cache_root = tmp_path / "cache"
    store = CacheStore(cache_root)
    store.write_page(
        source_url="https://www.pku.edu.cn/teacher/included",
        final_url="https://www.pku.edu.cn/teacher/included",
        university="北京大学",
        department="信息科学技术学院",
        status_code=200,
        content="王五\n职称：教授".encode(),
        headers={"content-type": "text/html; charset=utf-8"},
        encoding="utf-8",
        source_id="pku-profile-included",
        source_type="teacher_profile",
        fetched_at=datetime(2026, 6, 18, tzinfo=UTC),
    )
    store.write_page(
        source_url="https://www.pku.edu.cn/teacher/excluded",
        final_url="https://www.pku.edu.cn/teacher/excluded",
        university="北京大学",
        department="信息科学技术学院",
        status_code=200,
        content="赵六\n职称：教授".encode(),
        headers={"content-type": "text/html; charset=utf-8"},
        encoding="utf-8",
        source_id="pku-profile-excluded",
        source_type="teacher_profile",
        fetched_at=datetime(2026, 6, 18, tzinfo=UTC),
    )
    sources = tmp_path / "sources.yaml"
    sources.write_text(
        """
version: 1
universities:
  - id: pku
    name_zh: 北京大学
    name_en: Peking University
    allowed_domains:
      - pku.edu.cn
      - '*.pku.edu.cn'
    entries:
      - id: pku-profile-included
        url: https://www.pku.edu.cn/teacher/included
        type: teacher_profile
        department: 信息科学技术学院
        name_hint: 王五
""".strip(),
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    assert (
        main(
            [
                "extract-cache",
                "--cache-root",
                str(cache_root),
                "--out-dir",
                str(out_dir),
                "--sources",
                str(sources),
            ]
        )
        == 0
    )

    teachers = pq.read_table(out_dir / "teachers.parquet").to_pylist()
    assert [row["name"] for row in teachers] == ["王五"]
