from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from advisors.privacy import clean_excluded_text, contains_excluded_value


PARSER_NAME = "extract.cached_text_minimal"
PARSER_VERSION = "0.1.1"

_EMAIL_RE = re.compile(r"(?<![A-Za-z0-9._%+-])([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")
_NAME_PREFIX_RE = re.compile(r"^(?:姓名|教师姓名|Name)\s*[:：]?\s*", re.IGNORECASE)
_INVISIBLE_TEXT_RE = re.compile(r"[\ufeff\u200b\u200c\u200d\u2060]")
_CHINESE_NAME_RE = re.compile(r"^[\u3400-\u9fff·]{2,8}$")
_ENGLISH_LINE_RE = re.compile(r"^[A-Za-z][A-Za-z .,'-]{1,80}$")
_ENGLISH_NAME_RE = re.compile(
    r"^[A-Za-z][A-Za-z.'-]*(?:\s+[A-Za-z][A-Za-z.'-]*){1,4}$"
)
_HOMEPAGE_TITLE_SUFFIX_RE = re.compile(
    r"\s*(?:-{1,}|[|_])\s*(?:中文主页|英文主页|个人主页|教师主页|主页|首页|home).*$",
    re.IGNORECASE,
)
_UNIVERSITY_TITLE_PREFIX_RE = re.compile(r"^(?:清华大学|北京大学)\s*")
_BIRTH_DATE_RE = re.compile(
    r"(?:出生日期|出生年月|出生)\s*[:：]?\s*"
    r"((?:18|19|20)\d{2}(?:[-/.年]\d{1,2}(?:[-/.月]\d{1,2}日?)?)?)"
)
_ADDRESS_RE = re.compile(r"(?:办公地址|办公地点|办公室|Office)\s*[:：]?\s*(?P<value>.+)", re.IGNORECASE)
_RESEARCH_RE = re.compile(r"(?:研究方向|研究领域|研究兴趣|主要研究方向)\s*[:：]?\s*(?P<value>.+)")
_TITLE_LABEL_RE = re.compile(
    r"^\s*(?:职称|职位|职务|Title)\s*(?:[:：]|\s+)\s*(?P<value>.+)$",
    re.IGNORECASE,
)

_TITLE_KEYWORDS = (
    "长聘副教授",
    "长聘教授",
    "助理教授",
    "副研究员",
    "副教授",
    "研究员",
    "教授",
    "讲师",
    "院士",
    "博士后",
)
_STANDALONE_TITLE_KEYWORDS = tuple(
    keyword for keyword in _TITLE_KEYWORDS if keyword not in {"院士", "博士后"}
)

_PERSONAL_INFO_HEADINGS = {
    "个人信息",
    "基本信息",
    "个人资料",
    "教师信息",
    "个人概况",
}

_NAME_NOISE_TERMS = (
    "教师",
    "教师队伍",
    "师资",
    "师资队伍",
    "师资力量",
    "专任教师",
    "新闻",
    "更多",
    "详情",
    "首页",
    "主页",
    "中文主页",
    "英文主页",
    "个人主页",
    "教师主页",
    "english",
    "栏目",
    "导航",
)

_SECTION_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("research", ("研究方向", "研究领域", "研究兴趣", "主要研究方向", "研究课题")),
    ("biography", ("个人简介", "简介", "个人概况", "教育背景", "工作经历", "学术经历")),
    ("projects", ("科研项目", "研究项目", "项目", "基金", "课题")),
    ("publications", ("代表性成果", "科研成果", "发表论文", "论文", "著作", "出版物", "Publications")),
    ("honors", ("荣誉", "奖励", "获奖")),
    ("teaching", ("教学", "课程")),
    ("contact", ("联系方式", "联系信息", "邮箱", "办公地址", "办公地点", "办公室")),
)


def extract_profile_text(
    *,
    profile_id: str,
    source_url: str,
    university: str,
    fetched_at: str,
    text: str,
    person_id: str | None = None,
    department: str | None = None,
    homepage_url: str | None = None,
    name: str | None = None,
) -> dict[str, list[dict[str, object]]]:
    cleaned_text = clean_excluded_text(text)
    lines = _nonempty_lines(cleaned_text)
    primary_name = _infer_name(name, lines)
    homepage = homepage_url or source_url
    attributes = _extract_attributes(cleaned_text, lines)
    title = _first_attribute_value(attributes, "title")

    base = {
        "profile_id": profile_id,
        "person_id": person_id,
        "source_url": source_url,
        "fetched_at": fetched_at,
        "parser_name": PARSER_NAME,
        "parser_version": PARSER_VERSION,
    }

    result: dict[str, list[dict[str, object]]] = {
        "teachers": [
            {
                **base,
                "university": university,
                "department": department,
                "homepage_url": homepage,
                "name": primary_name,
                "primary_name": primary_name,
                "title": title,
                "person_id_status": "provided" if person_id else "unassigned",
                "identity_confidence": 1.0 if person_id else 0.0,
            }
        ],
        "teacher_names": [],
        "teacher_attributes": [],
        "teacher_sections": [],
    }

    if primary_name:
        result["teacher_names"].append(
            {
                **base,
                "name_value": primary_name,
                "name_type": "primary",
            }
        )

    for attribute_type, value in attributes:
        result["teacher_attributes"].append(
            {
                **base,
                "attr_key": attribute_type,
                "attr_value": value,
                "confidence": 0.8,
                "extractor": PARSER_NAME,
            }
        )

    for section in _extract_sections(lines):
        result["teacher_sections"].append(
            {
                **base,
                "section_type": section["section_type"],
                "section_title": section["section_title"],
                "section_text": section["section_text"],
            }
        )

    return _sanitize_result(result)


def _extract_attributes(text: str, lines: list[str]) -> list[tuple[str, str]]:
    attributes: list[tuple[str, str]] = []

    for email in _unique(match.group(1) for match in _EMAIL_RE.finditer(text)):
        if contains_excluded_value(email):
            continue
        attributes.append(("email", email))

    for line in lines:
        for title in _titles_from_line(line):
            attributes.append(("title", title))

        birth_date = _first_group(_BIRTH_DATE_RE.search(line), "value")
        if birth_date:
            attributes.append(("birth_date", birth_date))

        address_match = _ADDRESS_RE.search(line)
        if address_match:
            attributes.append(("office_address", address_match.group("value")))

        research_match = _RESEARCH_RE.search(line)
        if research_match:
            attributes.append(("research_direction", research_match.group("value")))

    return _dedupe_pairs(attributes)


def _extract_sections(lines: list[str]) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    current_type: str | None = None
    current_title: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_type, current_title, current_lines
        if current_type and current_title and current_lines:
            text = clean_excluded_text("\n".join(current_lines))
            if text:
                sections.append(
                    {
                        "section_type": current_type,
                        "section_title": current_title,
                        "section_text": text,
                    }
                )
        current_type = None
        current_title = None
        current_lines = []

    for line in lines:
        match = _section_heading(line)
        if match:
            flush()
            current_type, current_title, body = match
            if body:
                current_lines.append(body)
            continue

        keyword_match = _keyword_section_line(line)
        if keyword_match and not current_type:
            section_type, section_title = keyword_match
            sections.append(
                {
                    "section_type": section_type,
                    "section_title": section_title,
                    "section_text": clean_excluded_text(line),
                }
            )
            continue

        if current_type:
            current_lines.append(line)

    flush()
    return sections


def _section_heading(line: str) -> tuple[str, str, str] | None:
    stripped = re.sub(r"^\s*(?:[一二三四五六七八九十\d]+[、.．])\s*", "", line).strip()
    for section_type, keywords in _SECTION_KEYWORDS:
        for keyword in keywords:
            if not stripped.lower().startswith(keyword.lower()):
                continue
            tail = stripped[len(keyword) :].strip()
            if not tail:
                return section_type, keyword, ""
            if tail[0] in ":：":
                return section_type, keyword, tail[1:].strip()
            if len(stripped) <= len(keyword) + 8:
                return section_type, stripped, ""
    return None


def _keyword_section_line(line: str) -> tuple[str, str] | None:
    if len(line) > 300:
        return None
    lowered = line.lower()
    for section_type, keywords in _SECTION_KEYWORDS:
        for keyword in keywords:
            if keyword.lower() in lowered:
                return section_type, keyword
    return None


def _titles_from_line(line: str) -> list[str]:
    values: list[str] = []
    normalized = _normalize_text(line)
    label_match = _TITLE_LABEL_RE.search(normalized)
    if label_match:
        labelled_value = _conservative_title_value(label_match.group("value"))
        if labelled_value:
            values.append(labelled_value)

    if normalized in _STANDALONE_TITLE_KEYWORDS:
        values.append(normalized)

    return values


def _conservative_title_value(value: str) -> str | None:
    normalized = _normalize_text(clean_excluded_text(value))
    if not normalized:
        return None

    matches = [
        (match.start(), -(match.end() - match.start()), match.group(0))
        for keyword in _TITLE_KEYWORDS
        for match in re.finditer(re.escape(keyword), normalized)
    ]
    if not matches:
        return None

    return sorted(matches)[0][2]


def _infer_name(explicit_name: str | None, lines: list[str]) -> str | None:
    if explicit_name:
        explicit = _extract_explicit_name(explicit_name)
        if explicit:
            return explicit

    personal_info_name = _name_from_personal_info(lines)
    if personal_info_name:
        return personal_info_name

    if lines:
        return _extract_chinese_name(lines[0], clean_homepage_title=True)
    return None


def _name_from_personal_info(lines: list[str]) -> str | None:
    for index, line in enumerate(lines):
        if not _is_personal_info_heading(line):
            continue
        for candidate in lines[index + 1 : index + 10]:
            if _is_personal_info_heading(candidate):
                continue
            if _is_later_profile_section(candidate):
                break
            name = _extract_chinese_name(candidate)
            if name:
                return name
    return None


def _extract_explicit_name(candidate: str) -> str | None:
    cleaned = _clean_name_candidate(candidate)
    if not cleaned:
        return None

    compact = re.sub(r"\s+", "", cleaned)
    if _is_likely_chinese_name(compact):
        return compact

    if _is_likely_english_name(cleaned):
        return cleaned
    return None


def _extract_chinese_name(candidate: str, *, clean_homepage_title: bool = False) -> str | None:
    cleaned = _clean_name_candidate(candidate, clean_homepage_title=clean_homepage_title)
    if not cleaned:
        return None

    compact = re.sub(r"\s+", "", cleaned)
    if _is_likely_chinese_name(compact):
        return compact

    for part in re.split(r"[\s,，;；/]+", cleaned):
        if _is_likely_chinese_name(part):
            return part
    return None


def _clean_name_candidate(candidate: str, *, clean_homepage_title: bool = False) -> str | None:
    normalized = _normalize_text(candidate)
    if not _has_text_signal(normalized):
        return None

    cleaned = clean_excluded_text(_NAME_PREFIX_RE.sub("", normalized))
    cleaned = _normalize_text(cleaned)
    cleaned = _HOMEPAGE_TITLE_SUFFIX_RE.sub("", cleaned)
    if clean_homepage_title:
        cleaned = _UNIVERSITY_TITLE_PREFIX_RE.sub("", cleaned)
    cleaned = _normalize_text(cleaned.strip(" -_|:："))
    return cleaned or None


def _is_likely_chinese_name(value: str) -> bool:
    return bool(_CHINESE_NAME_RE.fullmatch(value)) and not _is_name_noise(value)


def _is_likely_english_name(value: str) -> bool:
    normalized = _normalize_text(value)
    if _is_name_noise(normalized, treat_english_as_noise=False):
        return False
    return bool(_ENGLISH_NAME_RE.fullmatch(normalized))


def _is_personal_info_heading(line: str) -> bool:
    return _normalize_text(line).strip(" :：") in _PERSONAL_INFO_HEADINGS


def _is_later_profile_section(line: str) -> bool:
    return bool(_section_heading(line) or _keyword_section_line(line))


def _is_name_noise(value: str, *, treat_english_as_noise: bool = True) -> bool:
    normalized = _normalize_text(value)
    lowered = normalized.lower()
    if not normalized or lowered in _NAME_NOISE_TERMS:
        return True
    if treat_english_as_noise and _ENGLISH_LINE_RE.fullmatch(normalized):
        return True
    if any(term in lowered for term in _NAME_NOISE_TERMS):
        return True
    return any(keyword == normalized or keyword in normalized for keyword in _TITLE_KEYWORDS)


def _nonempty_lines(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = _normalize_text(line)
        if stripped and _has_text_signal(stripped):
            lines.append(stripped)
    return lines


def _normalize_text(value: str) -> str:
    return _INVISIBLE_TEXT_RE.sub("", value).strip()


def _has_text_signal(value: str) -> bool:
    return any(character.isalnum() for character in value)


def _first_group(match: re.Match[str] | None, group_name: str) -> str | None:
    if not match:
        return None
    if group_name in match.groupdict():
        return match.group(group_name)
    return match.group(1)


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        cleaned = clean_excluded_text(value)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique_values.append(cleaned)
    return unique_values


def _dedupe_pairs(values: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[tuple[str, str]] = []
    for key, value in values:
        cleaned = clean_excluded_text(value)
        if not cleaned:
            continue
        item = (key, cleaned)
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _first_attribute_value(attributes: Iterable[tuple[str, str]], key: str) -> str | None:
    for attr_key, attr_value in attributes:
        if attr_key == key:
            return attr_value
    return None


def _sanitize_result(
    result: dict[str, list[dict[str, object]]],
) -> dict[str, list[dict[str, object]]]:
    sanitized: dict[str, list[dict[str, object]]] = {}
    required_payload = {
        "teacher_names": "name_value",
        "teacher_attributes": "attr_value",
        "teacher_sections": "section_text",
    }

    for table_name, rows in result.items():
        sanitized_rows: list[dict[str, object]] = []
        for row in rows:
            cleaned_row = {key: _sanitize_value(value) for key, value in row.items()}
            payload_key = required_payload.get(table_name)
            if payload_key and not cleaned_row.get(payload_key):
                continue
            sanitized_rows.append(cleaned_row)
        sanitized[table_name] = sanitized_rows
    return sanitized


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return _normalize_text(clean_excluded_text(_normalize_text(value)))
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_value(item) for item in value)
    if isinstance(value, dict):
        return {key: _sanitize_value(item) for key, item in value.items()}
    return value
