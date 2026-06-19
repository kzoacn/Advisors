from __future__ import annotations

from collections.abc import Iterable

from advisors.extract import extract_profile_text
from advisors.privacy import clean_excluded_text, contains_excluded_value, find_excluded_values


def test_extract_scrubs_excluded_values_from_all_structured_rows() -> None:
    rows = extract_profile_text(
        profile_id="tsinghua-zhangsan-001",
        person_id="person-001",
        source_url="https://www.cs.tsinghua.edu.cn/info/teacher/zhangsan.htm",
        university="清华大学",
        department="计算机系",
        homepage_url="https://www.cs.tsinghua.edu.cn/info/teacher/zhangsan.htm",
        fetched_at="2026-06-18T10:00:00+08:00",
        text="""张三
职称：教授
邮箱：zhangsan@tsinghua.edu.cn
办公地址：清华大学信息楼 302
手机：13800138000
电话：010-62781234
传真：+86 10 62785678
身份证号：110105198001011234
62797001-808
研究方向：人工智能，数据治理
科研项目：国家自然科学基金项目，联系电话 62781234
""",
    )

    flattened = "\n".join(_flatten_strings(rows))
    assert "zhangsan@tsinghua.edu.cn" in flattened
    assert "清华大学信息楼 302" in flattened
    assert "13800138000" not in flattened
    assert "010-62781234" not in flattened
    assert "62781234" not in flattened
    assert "62797001-808" not in flattened
    assert "62785678" not in flattened
    assert "110105198001011234" not in flattened
    assert not contains_excluded_value(flattened)

    assert rows["teachers"][0]["name"] == "张三"
    assert rows["teachers"][0]["primary_name"] == "张三"
    assert rows["teachers"][0]["title"] == "教授"
    assert rows["teachers"][0]["person_id_status"] == "provided"
    assert any(
        row["attr_key"] == "email"
        and row["attr_value"] == "zhangsan@tsinghua.edu.cn"
        and row["extractor"] == "extract.cached_text_minimal"
        and row["confidence"] > 0
        for row in rows["teacher_attributes"]
    )
    assert all("attr_key" in row and "attr_value" in row for row in rows["teacher_attributes"])
    assert all("section_text" in row for row in rows["teacher_sections"])
    assert any(
        row["section_type"] == "projects" and "国家自然科学基金项目" in row["section_text"]
        for row in rows["teacher_sections"]
    )
    assert all(
        row["source_url"] == "https://www.cs.tsinghua.edu.cn/info/teacher/zhangsan.htm"
        for table_rows in rows.values()
        for row in table_rows
    )


def test_clean_excluded_text_keeps_allowed_public_email_and_office_address() -> None:
    text = "邮箱：li.si@pku.edu.cn 电话：77701 办公地址：理科楼 201 传真：01062781234"
    cleaned = clean_excluded_text(text)

    assert "li.si@pku.edu.cn" in cleaned
    assert "理科楼 201" in cleaned
    assert "77701" not in cleaned
    assert "01062781234" not in cleaned
    assert "电话" not in cleaned
    assert "传真" not in cleaned
    assert not contains_excluded_value(cleaned)


def test_clean_excluded_text_removes_standalone_phone_style_lines() -> None:
    text = """邮箱：62781234@tsinghua.edu.cn
62781234
77701
62797001-808
01062781234
研究方向：数据库
"""

    cleaned = clean_excluded_text(text)

    assert "62781234@tsinghua.edu.cn" in cleaned
    assert "研究方向：数据库" in cleaned
    assert "62781234\n" not in cleaned
    assert "77701" not in cleaned
    assert "62797001-808" not in cleaned
    assert "01062781234" not in cleaned
    assert not contains_excluded_value(cleaned)


def test_clean_excluded_text_removes_parenthesized_area_code_landlines() -> None:
    for value in (
        "(010)62781234",
        "（010）62781234",
        "(010) 6278 1234",
        "010）62781234",
        "(010) 6278-1234",
    ):
        hits = find_excluded_values(value)
        assert any(hit.kind == "landline_phone" and hit.value == value for hit in hits), value
        assert contains_excluded_value(value), value

        cleaned = clean_excluded_text(
            f"邮箱：teacher@pku.edu.cn\n论文编号：PKU-2021-001\n电话：{value}\n"
        )

        assert "teacher@pku.edu.cn" in cleaned
        assert "PKU-2021-001" in cleaned
        assert value not in cleaned
        assert "电话" not in cleaned
        assert not contains_excluded_value(cleaned)


def test_clean_excluded_text_removes_additional_phone_formats() -> None:
    text = """邮箱：teacher@pku.edu.cn
出生日期：1988-07-12
任职时间：2006—2014
办公室：理科楼（62755617）
电话：010－6275－5617
英国校区：+44 1865 957600
"""

    cleaned = clean_excluded_text(text)

    assert "teacher@pku.edu.cn" in cleaned
    assert "1988-07-12" in cleaned
    assert "2006—2014" in cleaned
    assert "62755617" not in cleaned
    assert "010－6275－5617" not in cleaned
    assert "+44 1865 957600" not in cleaned
    assert "电话" not in cleaned
    assert not contains_excluded_value(cleaned)


def test_parenthesized_local_phone_needs_contact_context() -> None:
    text = "地址：北京市海淀区颐和园路5号（62755617） 反馈意见：its@pku.edu.cn"

    cleaned = clean_excluded_text(text)

    assert "62755617" not in cleaned
    assert "its@pku.edu.cn" in cleaned
    assert not contains_excluded_value(cleaned)

    assert not contains_excluded_value("《在娱乐与革命之间（1878-1937）》")
    assert not contains_excluded_value("国家自然基金面上项目（32070184），2021-2024年")
    assert not contains_excluded_value("Nat. Chem. 2025\n17\n1275–1283\n2.")
    assert not contains_excluded_value("联系历史研究项目(1954-1975)")


def test_standalone_phone_line_removes_grouped_local_numbers_without_years() -> None:
    for value in ("62781234", "6278 1234", "6278-1234"):
        hits = find_excluded_values(value)
        assert any(hit.kind == "standalone_phone_line" and hit.value == value for hit in hits), value
        assert contains_excluded_value(value), value

    assert not contains_excluded_value("2020-2021")
    assert not contains_excluded_value("论文编号：6278-1234")
    assert not contains_excluded_value("邮箱：li.si@pku.edu.cn")

    text = """发表年份：2020
2020-2021
论文编号：6278-1234
邮箱：li.si@pku.edu.cn
62781234
6278 1234
6278-1234
"""

    cleaned = clean_excluded_text(text)
    cleaned_lines = cleaned.splitlines()

    assert "发表年份：2020" in cleaned
    assert "2020-2021" in cleaned
    assert "论文编号：6278-1234" in cleaned
    assert "li.si@pku.edu.cn" in cleaned
    assert "62781234" not in cleaned_lines
    assert "6278 1234" not in cleaned_lines
    assert "6278-1234" not in cleaned_lines
    assert not contains_excluded_value(cleaned)


def test_privacy_detector_flags_mobile_local_part_email_but_keeps_numeric_email() -> None:
    text = (
        "邮箱：18101062399@163.com；备用：13801138669@163.com；"
        "变体：18668900804l@sina.com；"
        "数字邮箱：1605028280@qq.com；短数字邮箱：83229078@qq.com"
    )

    hits = find_excluded_values(text)

    assert any(
        hit.kind == "mobile_local_email" and hit.value == "18101062399@163.com"
        for hit in hits
    )
    assert any(
        hit.kind == "mobile_local_email" and hit.value == "13801138669@163.com"
        for hit in hits
    )
    assert contains_excluded_value("18101062399@163.com")
    assert contains_excluded_value("18668900804l@sina.com")
    assert not contains_excluded_value("1605028280@qq.com")
    assert not contains_excluded_value("83229078@qq.com")


def test_clean_excluded_text_removes_mobile_local_part_email_but_keeps_normal_email() -> None:
    text = """邮箱：18101062399@163.com
备用邮箱：13801138669@163.com；普通邮箱：zhangsan@pku.edu.cn
变体邮箱：18668900804l@sina.com
数字邮箱：1605028280@qq.com
短数字邮箱：83229078@qq.com
"""

    cleaned = clean_excluded_text(text)

    assert "18101062399@163.com" not in cleaned
    assert "13801138669@163.com" not in cleaned
    assert "18668900804l@sina.com" not in cleaned
    assert "18101062399" not in cleaned
    assert "13801138669" not in cleaned
    assert "18668900804" not in cleaned
    assert "zhangsan@pku.edu.cn" in cleaned
    assert "1605028280@qq.com" in cleaned
    assert "83229078@qq.com" in cleaned
    assert not contains_excluded_value(cleaned)


def test_privacy_detector_flags_standalone_and_labelled_short_phone_values() -> None:
    for text in ("62781234", "77701", "62797001-808", "01062781234", "电话：77701"):
        assert contains_excluded_value(text), text


def test_privacy_detector_finds_common_excluded_values() -> None:
    hits = find_excluded_values(
        "手机 13900001111；办公电话 010-62781234；身份证号 110105198001011234"
    )

    assert {hit.kind for hit in hits} >= {
        "mobile_phone",
        "landline_phone",
        "identity_document",
    }


def test_clean_excluded_text_removes_v3_tsinghua_phone_residuals_but_keeps_emails() -> None:
    text = """教授，博士生导师通信地址： 北京清华大学土木工程系邮编： 100084号码： 13910025639E-mail： dongcong@tsinghua.edu.cn教育背景
教授通讯地址：北京海淀区清华大学土木工程系(何善衡楼)邮编：100084010-62772457Email：niejg@mail.tsinghua.edu.cn
教授通信地址：北京市海淀区清华大学土木工程系邮编：100084010-62782708Email: shiyj@tsinghua.edu.cn
副教授通信地址：清华大学土木工程系地球空间信息研究所邮编： 100084号码：010-62782682E-mail：zbai@tsinghua.edu.cn
职称：教授 | +86 10 6277 2917 | E-mail address：zhanghq@tsinghua.edu.cn
(Lab.),62780550（Lab.）
"""

    cleaned = clean_excluded_text(text)

    for email in (
        "dongcong@tsinghua.edu.cn",
        "niejg@mail.tsinghua.edu.cn",
        "shiyj@tsinghua.edu.cn",
        "zbai@tsinghua.edu.cn",
        "zhanghq@tsinghua.edu.cn",
    ):
        assert email in cleaned

    for private_fragment in (
        "13910025639",
        "010-62772457",
        "010-62782708",
        "010-62782682",
        "+86 10 6277 2917",
        "62780550",
    ):
        assert private_fragment not in cleaned

    for contact_label in ("电话", "传真", "手机", "号码"):
        assert contact_label not in cleaned
    assert not contains_excluded_value(cleaned)


def test_extract_keeps_v3_tsinghua_titles_conservative_and_scrubs_contacts() -> None:
    rows = extract_profile_text(
        profile_id="tsinghua-civil-v3-residual-001",
        source_url="https://www.civil.tsinghua.edu.cn/info/teacher/example.htm",
        university="清华大学",
        department="土木工程系",
        fetched_at="2026-06-18T10:00:00+08:00",
        text="""董聪
个人信息
董聪
职称：教授，博士生导师通信地址： 北京清华大学土木工程系邮编： 100084号码： 13910025639E-mail： dongcong@tsinghua.edu.cn教育背景
联系方式
职称：教授 | +86 10 6277 2917 | E-mail address：zhanghq@tsinghua.edu.cn
(Lab.),62780550（Lab.）
""",
    )

    flattened = "\n".join(_flatten_strings(rows))

    assert rows["teachers"][0]["title"] == "教授"
    assert any(
        row["attr_key"] == "title" and row["attr_value"] == "教授"
        for row in rows["teacher_attributes"]
    )
    assert not any(
        row["attr_key"] == "title"
        and any(fragment in row["attr_value"] for fragment in ("通信地址", "邮编", "E-mail", "Email"))
        for row in rows["teacher_attributes"]
    )
    assert "dongcong@tsinghua.edu.cn" in flattened
    assert "zhanghq@tsinghua.edu.cn" in flattened
    for private_fragment in ("13910025639", "+86 10 6277 2917", "62780550"):
        assert private_fragment not in flattened
    for contact_label in ("电话", "传真", "手机", "号码"):
        assert contact_label not in flattened
    assert not contains_excluded_value(flattened)


def test_extract_does_not_emit_mobile_local_part_email_attributes() -> None:
    rows = extract_profile_text(
        profile_id="pku-mobile-local-email-001",
        source_url="https://www.pku.edu.cn/teacher/mobile-local-email",
        university="北京大学",
        department=None,
        fetched_at="2026-06-18T10:00:00+08:00",
        text="""个人信息
李四
邮箱：18101062399@163.com
备用邮箱：13801138669@163.com
数字邮箱：1605028280@qq.com
短数字邮箱：83229078@qq.com
普通邮箱：zhangsan@pku.edu.cn
研究方向：数据治理
""",
    )

    flattened = "\n".join(_flatten_strings(rows))
    emails = [
        row["attr_value"]
        for row in rows["teacher_attributes"]
        if row["attr_key"] == "email"
    ]

    assert "18101062399@163.com" not in emails
    assert "13801138669@163.com" not in emails
    assert "1605028280@qq.com" in emails
    assert "83229078@qq.com" in emails
    assert "zhangsan@pku.edu.cn" in emails
    assert "18101062399" not in flattened
    assert "13801138669" not in flattened
    assert not contains_excluded_value(flattened)


def test_extract_cleans_professor_and_phd_advisor_title_to_professor() -> None:
    rows = extract_profile_text(
        profile_id="tsinghua-professor-phd-advisor-title-001",
        source_url="https://www.tsinghua.edu.cn/info/teacher/professor.htm",
        university="清华大学",
        department=None,
        fetched_at="2026-06-18T10:00:00+08:00",
        text="""个人信息
王强
职称：教授、博导
邮箱：wangqiang@tsinghua.edu.cn
""",
    )

    assert rows["teachers"][0]["title"] == "教授"
    assert any(
        row["attr_key"] == "title" and row["attr_value"] == "教授"
        for row in rows["teacher_attributes"]
    )
    assert not any(
        row["attr_key"] == "title" and "博导" in row["attr_value"]
        for row in rows["teacher_attributes"]
    )


def test_extract_prefers_explicit_chinese_name_over_first_text_line() -> None:
    rows = extract_profile_text(
        profile_id="pku-lisi-001",
        source_url="https://www.pku.edu.cn/teacher/lisi",
        university="北京大学",
        department=None,
        fetched_at="2026-06-18T10:00:00+08:00",
        text="教师主页\n个人信息\n王五\n邮箱：li.si@pku.edu.cn",
        name="李四",
    )

    assert rows["teachers"][0]["name"] == "李四"
    assert rows["teachers"][0]["primary_name"] == "李四"
    assert rows["teacher_names"][0]["name_value"] == "李四"
    assert rows["teacher_names"][0]["name_type"] == "primary"


def test_extract_prefers_explicit_english_name_over_first_text_line() -> None:
    rows = extract_profile_text(
        profile_id="tsinghua-wuji-en-001",
        source_url="https://www.cs.tsinghua.edu.cn/info/teacher/wuji.htm",
        university="清华大学",
        department="计算机系",
        fetched_at="2026-06-18T10:00:00+08:00",
        text="教师主页\n个人信息\n吴及\n邮箱：wuji@tsinghua.edu.cn",
        name="Wu Ji",
    )

    assert rows["teachers"][0]["name"] == "Wu Ji"
    assert rows["teachers"][0]["primary_name"] == "Wu Ji"
    assert rows["teacher_names"][0]["name_value"] == "Wu Ji"


def test_extract_ignores_noisy_explicit_name() -> None:
    for noisy_name in ("教授", "新闻", "教师队伍", ""):
        rows = extract_profile_text(
            profile_id="tsinghua-wuji-noise-001",
            source_url="https://www.cs.tsinghua.edu.cn/info/teacher/wuji.htm",
            university="清华大学",
            department="计算机系",
            fetched_at="2026-06-18T10:00:00+08:00",
            text="""教师队伍
个人信息
吴及
邮箱：wuji@tsinghua.edu.cn
""",
            name=noisy_name,
        )

        assert rows["teachers"][0]["name"] == "吴及"
        assert rows["teachers"][0]["primary_name"] == "吴及"
        assert rows["teacher_names"][0]["name_value"] == "吴及"


def test_extract_does_not_extract_title_from_long_sentence_with_academician() -> None:
    rows = extract_profile_text(
        profile_id="tsinghua-academician-news-001",
        source_url="https://www.tsinghua.edu.cn/info/news.htm",
        university="清华大学",
        department=None,
        fetched_at="2026-06-18T10:00:00+08:00",
        text="清华新闻网报道，多位院士参加了学院举办的学术论坛并作主题发言。",
        name="教师队伍",
    )

    assert rows["teachers"][0]["title"] is None
    assert not any(row["attr_key"] == "title" for row in rows["teacher_attributes"])


def test_extract_does_not_extract_title_from_standalone_academician_line() -> None:
    rows = extract_profile_text(
        profile_id="tsinghua-academician-line-001",
        source_url="https://www.tsinghua.edu.cn/info/teacher/academician.htm",
        university="清华大学",
        department=None,
        fetched_at="2026-06-18T10:00:00+08:00",
        text="""个人信息
王强
院士
邮箱：wangqiang@tsinghua.edu.cn
""",
    )

    assert rows["teachers"][0]["title"] is None
    assert not any(row["attr_key"] == "title" for row in rows["teacher_attributes"])


def test_extract_does_not_extract_title_from_unlabelled_postdoc_text() -> None:
    for profile_id, text in (
        (
            "tsinghua-postdoc-line-001",
            """个人信息
王强
博士后
邮箱：wangqiang@tsinghua.edu.cn
""",
        ),
        (
            "tsinghua-postdoc-column-001",
            """个人信息
王强
博士后科研流动站
邮箱：wangqiang@tsinghua.edu.cn
""",
        ),
        (
            "tsinghua-postdoc-sentence-001",
            """个人信息
王强
学院设有博士后科研流动站，欢迎优秀青年学者申请。
邮箱：wangqiang@tsinghua.edu.cn
""",
        ),
    ):
        rows = extract_profile_text(
            profile_id=profile_id,
            source_url=f"https://www.tsinghua.edu.cn/info/teacher/{profile_id}.htm",
            university="清华大学",
            department=None,
            fetched_at="2026-06-18T10:00:00+08:00",
            text=text,
        )

        assert rows["teachers"][0]["title"] is None, profile_id
        assert not any(row["attr_key"] == "title" for row in rows["teacher_attributes"]), profile_id


def test_extract_keeps_labelled_postdoc_title() -> None:
    rows = extract_profile_text(
        profile_id="tsinghua-postdoc-labelled-001",
        source_url="https://www.tsinghua.edu.cn/info/teacher/postdoc.htm",
        university="清华大学",
        department=None,
        fetched_at="2026-06-18T10:00:00+08:00",
        text="""个人信息
王强
职称：博士后
邮箱：wangqiang@tsinghua.edu.cn
""",
    )

    assert rows["teachers"][0]["title"] == "博士后"
    assert any(
        row["attr_key"] == "title" and row["attr_value"] == "博士后"
        for row in rows["teacher_attributes"]
    )


def test_extract_keeps_short_standalone_title_line() -> None:
    rows = extract_profile_text(
        profile_id="tsinghua-professor-title-001",
        source_url="https://www.cs.tsinghua.edu.cn/info/teacher/professor.htm",
        university="清华大学",
        department="计算机系",
        fetched_at="2026-06-18T10:00:00+08:00",
        text="""个人信息
冯建华
教授
邮箱：fengjh@tsinghua.edu.cn
""",
    )

    assert rows["teachers"][0]["title"] == "教授"
    assert any(
        row["attr_key"] == "title" and row["attr_value"] == "教授"
        for row in rows["teacher_attributes"]
    )


def test_extract_infers_chinese_name_after_personal_info_heading() -> None:
    rows = extract_profile_text(
        profile_id="tsinghua-wuji-001",
        source_url="https://www.cs.tsinghua.edu.cn/info/teacher/wuji.htm",
        university="清华大学",
        department="计算机系",
        fetched_at="2026-06-18T10:00:00+08:00",
        text="""清华大学 吴及--中文主页--首页
首页
English
个人信息
吴及
Wu Ji
教授
研究方向：人工智能
""",
    )

    assert rows["teachers"][0]["name"] == "吴及"
    assert rows["teachers"][0]["primary_name"] == "吴及"
    assert rows["teacher_names"][0]["name_value"] == "吴及"
    assert rows["teachers"][0]["title"] == "教授"


def test_extract_cleans_homepage_title_to_chinese_name() -> None:
    rows = extract_profile_text(
        profile_id="tsinghua-wuji-title-001",
        source_url="https://www.cs.tsinghua.edu.cn/info/teacher/wuji.htm",
        university="清华大学",
        department="计算机系",
        fetched_at="2026-06-18T10:00:00+08:00",
        text="清华大学 吴及--中文主页--首页\n邮箱：wuji@tsinghua.edu.cn\n",
    )

    assert rows["teachers"][0]["name"] == "吴及"
    assert rows["teachers"][0]["primary_name"] == "吴及"
    assert rows["teacher_names"][0]["name_value"] == "吴及"


def test_extract_ignores_bom_blank_and_symbol_only_name_lines() -> None:
    rows = extract_profile_text(
        profile_id="tsinghua-wangwu-001",
        source_url="https://www.cs.tsinghua.edu.cn/info/teacher/wangwu.htm",
        university="清华大学",
        department="计算机系",
        fetched_at="2026-06-18T10:00:00+08:00",
        text="\ufeff\n   \n-----\n姓名：王五\n邮箱：wangwu@tsinghua.edu.cn\n",
        name="\ufeff",
    )

    flattened = "\n".join(_flatten_strings(rows))
    assert rows["teachers"][0]["name"] == "王五"
    assert rows["teachers"][0]["primary_name"] == "王五"
    assert rows["teacher_names"][0]["name_value"] == "王五"
    assert "\ufeff" not in flattened


def _flatten_strings(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _flatten_strings(item)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _flatten_strings(item)
