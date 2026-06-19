from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ExcludedValue:
    kind: str
    value: str
    start: int
    end: int


_LEFT_BOUNDARY = r"(?<![A-Za-z0-9@])"
_RIGHT_BOUNDARY = r"(?![A-Za-z0-9@])"
_PHONE_SEP = r"[- \t－—–]"

_MOBILE_PHONE_RE = re.compile(
    rf"{_LEFT_BOUNDARY}(?:\+?86{_PHONE_SEP}*)?1[3-9](?:{_PHONE_SEP}*\d){{9}}{_RIGHT_BOUNDARY}"
)
_MOBILE_LOCAL_EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+-])1[3-9]\d{9}[A-Za-z]{0,3}@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    re.IGNORECASE,
)
_LANDLINE_PHONE_RE = re.compile(
    rf"{_LEFT_BOUNDARY}(?:"
    rf"\+?86{_PHONE_SEP}*(?:10|2\d|[3-9]\d{{2}}){_PHONE_SEP}*\d(?:{_PHONE_SEP}*\d){{6,7}}|"
    rf"0\d{{2,3}}{_PHONE_SEP}*\d(?:{_PHONE_SEP}*\d){{6,7}}|"
    rf"(?:10|2\d|[3-9]\d{{2}}){_PHONE_SEP}+\d(?:{_PHONE_SEP}*\d){{6,7}}"
    rf")(?:{_PHONE_SEP}*(?:转|ext\.?|分机){_PHONE_SEP}*\d{{1,5}})?{_RIGHT_BOUNDARY}",
    re.IGNORECASE,
)
_PARENTHESIZED_AREA_LANDLINE_RE = re.compile(
    rf"{_LEFT_BOUNDARY}(?:\+?86{_PHONE_SEP}*)?(?:[（(]\s*)?"
    rf"0?(?:10|2\d|[3-9]\d{{2}})\s*[)）]{_PHONE_SEP}*"
    rf"\d(?:{_PHONE_SEP}*\d){{6,7}}"
    rf"(?:{_PHONE_SEP}*(?:转|ext\.?|分机){_PHONE_SEP}*\d{{1,5}})?{_RIGHT_BOUNDARY}",
    re.IGNORECASE,
)
_CONTEXTUAL_PARENTHESIZED_LOCAL_PHONE_RE = re.compile(
    rf"(?i)(?:联系方式|联系地址|联系|办公(?:室|电话)?|固定电话|座机|电话|传真|"
    rf"地址|反馈意见|fax|tel(?:ephone)?|phone)"
    rf"(?P<context>.{{0,80}}?)"
    rf"(?P<value>[（(]\s*\d(?:[ \t]*\d){{6,7}}\s*[)）])"
)
_INTERNATIONAL_PHONE_RE = re.compile(
    rf"{_LEFT_BOUNDARY}\+\d{{1,3}}(?:{_PHONE_SEP}|[()（）])*\d"
    rf"(?:(?:{_PHONE_SEP}|[()（）])*\d){{6,13}}{_RIGHT_BOUNDARY}",
    re.IGNORECASE,
)
_POSTCODE_ADJOINED_LANDLINE_RE = re.compile(
    rf"(?<=\d{{6}})0\d{{2,3}}{_PHONE_SEP}*\d(?:{_PHONE_SEP}*\d){{6,7}}"
    rf"(?:{_PHONE_SEP}*(?:转|ext\.?|分机){_PHONE_SEP}*\d{{1,5}})?",
    re.IGNORECASE,
)
_LABELLED_LOCAL_PHONE_RE = re.compile(
    r"(?i)(?:联系电话|办公电话|固定电话|座机|手机|电话|传真|号码|"
    r"fax|tel(?:ephone)?|phone|mobile)\s*[:：#-]?\s*"
    rf"(?P<value>(?:\+?86{_PHONE_SEP}*)?(?:0\d{{2,3}}{_PHONE_SEP}*)?\d(?:{_PHONE_SEP}*\d){{4,11}}"
    rf"(?:(?:[- \t－—–]+|[ \t]*(?:转|ext\.?|分机)[ \t]*)\d{{1,5}})?)"
)
_LAB_PHONE_RE = re.compile(
    r"(?i)(?:[,，、;；]\s*)?\d{5,12}\s*[（(]\s*Lab\.?\s*[)）]"
)
_STANDALONE_PHONE_LINE_RE = re.compile(
    r"(?im)^[^\S\r\n]*"
    r"(?P<value>(?:"
    r"\d{5,12}(?:(?:[- \t]+|[ \t]*(?:转|ext\.?|分机)[ \t]*)\d{1,5})?|"
    r"(?!(?:18|19|20|21)\d{2}[- \t]+(?:18|19|20|21)\d{2}\b)"
    r"\d{4}[- \t]+\d{4}"
    r"(?:(?:[- \t]+|[ \t]*(?:转|ext\.?|分机)[ \t]*)\d{1,5})?"
    r"))"
    r"[^\S\r\n]*$"
)
_MAINLAND_ID_RE = re.compile(
    rf"{_LEFT_BOUNDARY}[1-9]\d{{5}}(?:18|19|20)\d{{2}}"
    rf"(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{{3}}[\dXx]{_RIGHT_BOUNDARY}"
)
_LABELLED_DOCUMENT_RE = re.compile(
    r"(?i)(?:身份证(?:号)?|证件(?:号码|号)?|护照(?:号|号码)?|"
    r"\bpassport\b\s*(?:no\.?|number)?|\bid\s*(?:no\.?|number)\b)\s*[:：#-]?\s*"
    r"(?P<value>[A-Z0-9][A-Z0-9 -]{5,24})"
)
_EXCLUDED_LABEL_TOKEN_RE = re.compile(
    r"(?i)(?:联系电话|办公电话|固定电话|座机|手机|电话|传真|号码|"
    r"身份证(?:号)?|证件(?:号码|号)?|护照(?:号|号码)?|"
    r"\bfax\b|\btel(?:ephone)?\b|\bphone\b|\bmobile\b|"
    r"\bpassport\b\s*(?:no\.?|number)?|\bid\s*(?:no\.?|number)\b)\s*[:：#-]?\s*"
)


def find_excluded_values(text: str | None) -> list[ExcludedValue]:
    if not text:
        return []

    hits: list[ExcludedValue] = []
    for kind, pattern in (
        ("mobile_local_email", _MOBILE_LOCAL_EMAIL_RE),
        ("international_phone", _INTERNATIONAL_PHONE_RE),
        ("mobile_phone", _MOBILE_PHONE_RE),
        ("landline_phone", _PARENTHESIZED_AREA_LANDLINE_RE),
        ("landline_phone", _LANDLINE_PHONE_RE),
        ("landline_phone", _POSTCODE_ADJOINED_LANDLINE_RE),
        ("lab_phone", _LAB_PHONE_RE),
        ("identity_document", _MAINLAND_ID_RE),
    ):
        for match in pattern.finditer(text):
            hits.append(ExcludedValue(kind, match.group(0), match.start(), match.end()))

    for match in _LABELLED_LOCAL_PHONE_RE.finditer(text):
        hits.append(
            ExcludedValue(
                "labelled_phone",
                match.group("value"),
                match.start("value"),
                match.end("value"),
            )
        )

    for match in _CONTEXTUAL_PARENTHESIZED_LOCAL_PHONE_RE.finditer(text):
        hits.append(
            ExcludedValue(
                "contextual_parenthesized_phone",
                match.group("value"),
                match.start("value"),
                match.end("value"),
            )
        )

    for match in _STANDALONE_PHONE_LINE_RE.finditer(text):
        hits.append(
            ExcludedValue(
                "standalone_phone_line",
                match.group("value"),
                match.start("value"),
                match.end("value"),
            )
        )

    for match in _LABELLED_DOCUMENT_RE.finditer(text):
        hits.append(
            ExcludedValue(
                "identity_document",
                match.group("value"),
                match.start("value"),
                match.end("value"),
            )
        )

    return _without_overlaps(hits)


def contains_excluded_value(text: str | None) -> bool:
    return bool(find_excluded_values(text))


def clean_excluded_text(text: str | None, *, replacement: str = "") -> str:
    if not text:
        return ""

    cleaned = str(text)
    for hit in sorted(find_excluded_values(cleaned), key=lambda item: item.start, reverse=True):
        cleaned = cleaned[: hit.start] + replacement + cleaned[hit.end :]

    cleaned = _EXCLUDED_LABEL_TOKEN_RE.sub("", cleaned)
    return _tidy_cleaned_text(cleaned)


def _without_overlaps(hits: list[ExcludedValue]) -> list[ExcludedValue]:
    selected: list[ExcludedValue] = []
    for hit in sorted(hits, key=lambda item: (item.start, -(item.end - item.start))):
        if any(hit.start < kept.end and kept.start < hit.end for kept in selected):
            continue
        selected.append(hit)
    return selected


def _tidy_cleaned_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"[ \t]*([,，;；])[ \t]*", r"\1", text)
    text = re.sub(r"([,，;；]){2,}", r"\1", text)

    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip(" \t,，;；:：#-")
        if stripped:
            lines.append(stripped)
    return "\n".join(lines)
