from datetime import UTC, datetime

from advisors.cache import CacheStore
from advisors.discover import (
    discover_profiles_from_cache,
    discover_tsinghua_faculty_lists_from_cache,
    discover_tsinghua_profiles_from_cache,
    discover_tsinghua_units_from_cache,
)


def test_discover_tsinghua_profiles_from_faculty_list(tmp_path) -> None:
    store = CacheStore(tmp_path)
    store.write_page(
        source_url="https://www.cs.tsinghua.edu.cn/szzk/jzgml.htm",
        final_url="https://www.cs.tsinghua.edu.cn/szzk/jzgml.htm",
        university="清华大学",
        department="计算机科学与技术系",
        status_code=200,
        content="""
        <html><body>
          <a href="../info/1111/3490.htm">冯建华</a>
          <a href="../info/1111/3490.htm">冯建华</a>
          <a href="../info/1177/126613.htm">新闻</a>
          <a href="https://example.com/info/1111/3491.htm">外站</a>
        </body></html>
        """.encode(),
        headers={"content-type": "text/html; charset=utf-8"},
        encoding="utf-8",
        source_id="thu-cs-faculty-list",
        source_type="faculty_list",
        fetched_at=datetime(2026, 6, 18, tzinfo=UTC),
    )

    sources = discover_tsinghua_profiles_from_cache(tmp_path)

    assert len(sources) == 1
    assert sources[0].url == "https://www.cs.tsinghua.edu.cn/info/1111/3490.htm"
    assert sources[0].type == "teacher_profile"
    assert sources[0].department == "计算机科学与技术系"


def test_discover_tsinghua_profile_system_links(tmp_path) -> None:
    store = CacheStore(tmp_path)
    store.write_page(
        source_url="https://www.ee.tsinghua.edu.cn/people.htm",
        final_url="https://www.ee.tsinghua.edu.cn/people.htm",
        university="清华大学",
        department="电子工程系",
        status_code=200,
        content="""
        <html><body>
          <a href="https://web.ee.tsinghua.edu.cn/wuji/zh_CN/index.htm">吴及</a>
        </body></html>
        """.encode(),
        headers={"content-type": "text/html; charset=utf-8"},
        encoding="utf-8",
        source_type="faculty_list",
        fetched_at=datetime(2026, 6, 18, tzinfo=UTC),
    )

    sources = discover_tsinghua_profiles_from_cache(tmp_path)

    assert [source.url for source in sources] == [
        "https://web.ee.tsinghua.edu.cn/wuji/zh_CN/index.htm"
    ]


def test_discover_profile_system_links_extracts_name_from_card_text(tmp_path) -> None:
    store = CacheStore(tmp_path)
    store.write_page(
        source_url="https://gr.xjtu.edu.cn/",
        final_url="https://gr.xjtu.edu.cn/",
        university="西安交通大学",
        department=None,
        status_code=200,
        content="""
        <html><body>
          <a href="https://gr.xjtu.edu.cn/zhengyu.zhao/zh_CN/index.htm">
            赵正宇 赵正宇 教授 、 博士生导师 电子与信息学部-网络空间安全学院
          </a>
        </body></html>
        """.encode(),
        headers={"content-type": "text/html; charset=utf-8"},
        encoding="utf-8",
        source_type="profile_index",
        fetched_at=datetime(2026, 6, 18, tzinfo=UTC),
    )

    sources = discover_profiles_from_cache(
        tmp_path,
        university_name_zh="西安交通大学",
        source_id_prefix="xjtu-profile",
        allowed_domains=["xjtu.edu.cn", "*.xjtu.edu.cn"],
    )

    assert [(source.url, source.anchor_text) for source in sources] == [
        ("https://gr.xjtu.edu.cn/zhengyu.zhao/zh_CN/index.htm", "赵正宇")
    ]


def test_discover_profiles_rejects_non_name_anchors_and_pdfs(tmp_path) -> None:
    store = CacheStore(tmp_path)
    store.write_page(
        source_url="https://school.sjtu.edu.cn/faculty/",
        final_url="https://school.sjtu.edu.cn/faculty/",
        university="上海交通大学",
        department="示例学院",
        status_code=200,
        content="""
        <html><body>
          <a href="/teacher/zhangsan">张三</a>
          <a href="/news/detail.html">了解更多</a>
          <a href="/kindeditor/Upload/file/20210421/demo.pdf">王琪</a>
        </body></html>
        """.encode(),
        headers={"content-type": "text/html; charset=utf-8"},
        encoding="utf-8",
        source_type="faculty_list",
        fetched_at=datetime(2026, 6, 18, tzinfo=UTC),
    )

    sources = discover_profiles_from_cache(
        tmp_path,
        university_name_zh="上海交通大学",
        source_id_prefix="sjtu-profile",
        allowed_domains=["sjtu.edu.cn", "*.sjtu.edu.cn"],
    )

    assert [source.url for source in sources] == ["https://school.sjtu.edu.cn/teacher/zhangsan"]


def test_discover_profiles_accepts_webplus_teacher_pages_with_decorated_names(tmp_path) -> None:
    store = CacheStore(tmp_path)
    store.write_page(
        source_url="https://cs.nju.edu.cn/2639/list.htm",
        final_url="https://cs.nju.edu.cn/2639/list.htm",
        university="南京大学",
        department="计算机学院",
        status_code=200,
        content="""
        <html><body>
          <a href="/58/2a/c2639a153642/page.htm">吕建 (院士、博导)</a>
          <a href="/_redirect?articleId=421500&columnId=11339&siteId=317">汪曙光</a>
          <a href="/_web/_platform/_teacherHome/web/login.jsp">教师登录入口</a>
        </body></html>
        """.encode(),
        headers={"content-type": "text/html; charset=utf-8"},
        encoding="utf-8",
        source_type="faculty_list",
        fetched_at=datetime(2026, 6, 18, tzinfo=UTC),
    )

    sources = discover_profiles_from_cache(
        tmp_path,
        university_name_zh="南京大学",
        source_id_prefix="nju-profile",
        allowed_domains=["nju.edu.cn", "*.nju.edu.cn"],
    )

    assert [(source.url, source.anchor_text) for source in sources] == [
        ("https://cs.nju.edu.cn/58/2a/c2639a153642/page.htm", "吕建")
    ]


def test_discover_profiles_accepts_year_based_webplus_teacher_pages(tmp_path) -> None:
    store = CacheStore(tmp_path)
    store.write_page(
        source_url="https://eeis.ustc.edu.cn/2648/list.htm",
        final_url="https://eeis.ustc.edu.cn/2648/list.htm",
        university="中国科学技术大学",
        department="电子工程与信息科学系",
        status_code=200,
        content="""
        <html><body>
          <a href="/2017/0807/c2648a190436/page.htm">陈畅</a>
          <a href="/2703/list.htm">学术活动</a>
        </body></html>
        """.encode(),
        headers={"content-type": "text/html; charset=utf-8"},
        encoding="utf-8",
        source_type="faculty_list",
        fetched_at=datetime(2026, 6, 18, tzinfo=UTC),
    )

    sources = discover_profiles_from_cache(
        tmp_path,
        university_name_zh="中国科学技术大学",
        source_id_prefix="ustc-profile",
        allowed_domains=["ustc.edu.cn", "*.ustc.edu.cn"],
    )

    assert [(source.url, source.anchor_text) for source in sources] == [
        ("https://eeis.ustc.edu.cn/2017/0807/c2648a190436/page.htm", "陈畅")
    ]


def test_discover_tsinghua_units_from_unit_index(tmp_path) -> None:
    store = CacheStore(tmp_path)
    store.write_page(
        source_url="https://www.tsinghua.edu.cn/yxsz.htm",
        final_url="https://www.tsinghua.edu.cn/yxsz.htm",
        university="清华大学",
        department=None,
        status_code=200,
        content="""
        <html><body>
          <a href="http://www.arch.tsinghua.edu.cn/">建筑学院</a>
          <a href="http://www.lib.tsinghua.edu.cn/">图书馆</a>
        </body></html>
        """.encode(),
        headers={"content-type": "text/html; charset=utf-8"},
        encoding="utf-8",
        source_type="unit_index",
        fetched_at=datetime(2026, 6, 18, tzinfo=UTC),
    )

    sources = discover_tsinghua_units_from_cache(tmp_path)

    assert len(sources) == 1
    assert sources[0].type == "unit_home"
    assert sources[0].department == "建筑学院"


def test_discover_tsinghua_faculty_lists_from_unit_home(tmp_path) -> None:
    store = CacheStore(tmp_path)
    store.write_page(
        source_url="https://www.example.tsinghua.edu.cn/",
        final_url="https://www.example.tsinghua.edu.cn/",
        university="清华大学",
        department="示例学院",
        status_code=200,
        content="""
        <html><body>
          <a href="/szdw/jsml.htm">师资队伍</a>
          <a href="/news.htm">新闻</a>
        </body></html>
        """.encode(),
        headers={"content-type": "text/html; charset=utf-8"},
        encoding="utf-8",
        source_type="unit_home",
        fetched_at=datetime(2026, 6, 18, tzinfo=UTC),
    )

    sources = discover_tsinghua_faculty_lists_from_cache(tmp_path)

    assert len(sources) == 1
    assert sources[0].type == "faculty_list"
    assert sources[0].url == "https://www.example.tsinghua.edu.cn/szdw/jsml.htm"


def test_discover_faculty_lists_rejects_news_with_professor_word(tmp_path) -> None:
    store = CacheStore(tmp_path)
    store.write_page(
        source_url="https://example.nju.edu.cn/",
        final_url="https://example.nju.edu.cn/",
        university="南京大学",
        department="示例学院",
        status_code=200,
        content="""
        <html><body>
          <a href="/teachers/list.htm">教授</a>
          <a href="/news/2026-report.htm">王某教授应邀做学术报告</a>
        </body></html>
        """.encode(),
        headers={"content-type": "text/html; charset=utf-8"},
        encoding="utf-8",
        source_type="unit_home",
        fetched_at=datetime(2026, 6, 18, tzinfo=UTC),
    )

    from advisors.discover import discover_faculty_lists_from_cache

    sources = discover_faculty_lists_from_cache(
        tmp_path,
        university_name_zh="南京大学",
        source_id_prefix="nju-faculty-list",
        allowed_domains=["nju.edu.cn", "*.nju.edu.cn"],
    )

    assert [source.url for source in sources] == ["https://example.nju.edu.cn/teachers/list.htm"]


def test_discover_faculty_lists_follows_cached_faculty_pagination(tmp_path) -> None:
    store = CacheStore(tmp_path)
    store.write_page(
        source_url="https://eeis.ustc.edu.cn/2648/list.htm",
        final_url="https://eeis.ustc.edu.cn/2648/list.htm",
        university="中国科学技术大学",
        department="电子工程与信息科学系",
        status_code=200,
        content="""
        <html><body>
          <a href="/2648/list2.htm">下一页&gt;&gt;</a>
          <a href="/2703/list.htm">学术活动</a>
        </body></html>
        """.encode(),
        headers={"content-type": "text/html; charset=utf-8"},
        encoding="utf-8",
        source_type="faculty_list",
        fetched_at=datetime(2026, 6, 18, tzinfo=UTC),
    )

    from advisors.discover import discover_faculty_lists_from_cache

    sources = discover_faculty_lists_from_cache(
        tmp_path,
        university_name_zh="中国科学技术大学",
        source_id_prefix="ustc-faculty-list",
        allowed_domains=["ustc.edu.cn", "*.ustc.edu.cn"],
    )

    assert [source.url for source in sources] == ["https://eeis.ustc.edu.cn/2648/list2.htm"]
