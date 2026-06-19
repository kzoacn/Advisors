from __future__ import annotations

import re
import hashlib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import yaml
from bs4 import BeautifulSoup

from advisors.cache import CacheRecord, CacheStore
from advisors.url_utils import host_matches, normalize_url


_ZH_NAME_RE = re.compile(r"^[\u4e00-\u9fff·]{2,4}$")
_PROFILE_PATH_RE = re.compile(r"/[A-Za-z0-9_.-]+/(?:zh_CN|en)/index\.htm$")
_WEBPLUS_PROFILE_PAGE_RE = re.compile(
    r"/(?:[0-9a-f]{2}/[0-9a-f]{2}|\d{4}/\d{4})/c\d+a\d+/page\.htm$",
    re.IGNORECASE,
)
_HTML_PAGE_RE = re.compile(r"(?:/|\\.)(?:html?|jsp)(?:$|[?#])", re.IGNORECASE)
_NON_PROFILE_URL_RE = re.compile(
    r"(?i)(?:/_redirect\b|/login\.jsp\b|/wfwpt\b|passport\.|ivpn\.|webvpn\.|/auth/login|[{}]|%7b|%7d)"
)
_NON_NAME_ANCHORS = {
    "留言板",
    "行政类",
    "科研类",
    "下载区",
    "关于我们",
    "委员会",
    "学院架构",
    "院长寄语",
    "组织体系",
    "精彩瞬间",
    "新闻动态",
    "外包公示",
    "大事记",
    "专著",
    "联系我们",
    "奖励荣誉",
    "历史沿革",
    "办事指南",
    "历史",
    "沿革",
    "概览",
    "概况",
    "教工之家",
    "办公服务",
    "教育教学",
    "研究生教育",
    "博士后",
    "工程系列",
    "光荣退休",
    "杰出人才",
    "教辅行政",
    "教学系列",
    "教研系列",
    "荣誉学衔",
    "研究系列",
    "师资队伍",
    "产学研合作",
    "关联机构",
    "科研基地",
    "科研项目",
    "研究机构",
    "学科建设",
    "学生工作",
    "学工通知",
    "学生动态",
    "教务通知",
    "讲座信息",
    "科研通知",
    "留学生项目",
    "暑期夏令营",
    "国际化",
    "院士",
    "党团建设",
    "院友",
    "基金捐赠",
    "院友活动",
    "院友之家",
    "招贤纳士",
    "教务部",
    "关注",
    "新闻",
    "更多",
    "首页",
    "教师",
    "教授",
    "师资",
    "招聘",
    "通知",
    "公告",
    "学术",
    "科研",
    "教学",
    "查看",
    "详情",
    "更多>>",
    "内部文档",
    "我要投稿",
    "系室导航",
    "总体介绍",
    "组织框架",
    "教师名录",
    "本科生",
    "实习实践",
    "党群建设",
    "外事外联",
    "管理技术",
    "科技获奖",
    "工程硕士",
    "宣传视频",
    "党建思政",
    "组织领导",
    "党群风采",
    "校园门户",
    "教职员工",
    "公共平台",
    "师资团队",
    "中文首页",
    "资源",
    "培养",
    "学位",
    "导师",
    "专业硕士",
    "学术论文",
    "学术动态",
    "学术期刊",
    "学术报告",
    "学术交流",
    "学习园地",
    "学习资料",
    "媒体聚焦",
    "国际交流",
    "国际会议",
    "职业发展",
    "生涯发展",
    "定制课程",
    "微专业",
    "专业介绍",
    "友情链接",
    "院长致辞",
    "访问教授",
    "访问学者",
    "客座教授",
    "兼职教授",
    "兼聘教授",
    "全职教师",
    "荣休教师",
    "诚聘英才",
    "党务公开",
    "工会动态",
    "投票系统",
    "饮水思源",
    "汉语学习",
    "清能驿站",
    "采购问答",
    "党政信息",
    "关于文创",
    "返回列表",
    "查看详情",
    "查看更多",
    "了解更多",
    "成果专利",
    "授权专利",
    "下一页",
    "院长信箱",
    "高端培训",
    "永远怀念",
    "楼宇建筑",
    "师者风范",
    "外院快讯",
    "合同协议",
    "学术展厅",
    "生医工人",
    "育人名师",
    "上海市",
    "图集",
    "奖助补贷",
    "全球师资",
    "改革发展",
    "博导硕导",
    "视觉标识",
    "海外优青",
    "按职级",
    "正文",
    "国家",
    "学校",
    "全部",
    "登录",
    "搜索",
    "毕业留影",
    "政策文件",
    "规章制度",
    "学员心声",
    "在线办公",
    "博士生",
    "旧版网站",
    "理论武装",
    "师资力量",
    "网站首页",
    "内网入口",
    "教师登录入口",
    "热点专题",
    "南京大学",
    "生物系",
    "郑重声明",
    "本科生院",
    "图书馆",
    "广纳贤才",
    "就业信息",
    "薪酬福利",
    "产业联盟",
    "持股企业",
    "全部信息",
    "综合管理",
    "市场营销",
    "会计",
    "战略与创业",
    "组织与人力资源",
    "运筹",
    "运营管理",
    "管理信息系统",
    "金融",
    "概率与统计",
    "English",
}
_NON_NAME_SUBSTRINGS = (
    "学院",
    "项目",
    "新闻",
    "通知",
    "公告",
    "队伍",
    "教育",
    "教学",
    "科研",
    "党团",
    "院友",
    "基金",
    "捐赠",
    "活动",
    "之家",
    "招贤",
    "纳士",
    "教务",
    "关注",
    "院士",
    "文档",
    "投稿",
    "导航",
    "总体",
    "组织",
    "框架",
    "名录",
    "实践",
    "党群",
    "外事",
    "外联",
    "管理",
    "技术",
    "科技",
    "获奖",
    "工程",
    "硕士",
    "宣传",
    "视频",
    "党建",
    "思政",
    "领导",
    "风采",
    "门户",
    "员工",
    "平台",
    "团队",
    "资源",
    "培养",
    "学位",
    "导师",
    "论文",
    "动态",
    "期刊",
    "报告",
    "学习",
    "园地",
    "资料",
    "媒体",
    "聚焦",
    "职业",
    "生涯",
    "定制",
    "课程",
    "微专业",
    "专业",
    "介绍",
    "链接",
    "致辞",
    "访问",
    "客座",
    "兼职",
    "兼聘",
    "全职",
    "教授",
    "入口",
    "热点",
    "专题",
    "大学",
    "登录",
    "内网",
    "栏目",
    "生物系",
    "化学",
    "声明",
    "本科",
    "图书",
    "广纳",
    "贤才",
    "就业",
    "薪酬",
    "福利",
    "产业",
    "联盟",
    "企业",
    "全部",
    "综合",
    "市场",
    "营销",
    "会计",
    "战略",
    "创业",
    "人力",
    "运筹",
    "运营",
    "金融",
    "概率",
    "统计",
    "英才",
    "党务",
    "工会",
    "投票",
    "文创",
    "返回",
    "列表",
    "查看",
    "了解",
    "详情",
    "正文",
    "国家",
    "学校",
    "驿站",
    "采购",
    "培训",
    "专利",
    "决策",
    "咨询",
    "协议",
    "合同",
    "快讯",
    "信箱",
    "怀念",
    "楼宇",
    "建筑",
    "师者",
    "展厅",
    "名师",
    "图集",
    "奖助",
    "补贷",
    "全球",
    "改革",
    "发展",
    "博导",
    "硕导",
    "视觉",
    "标识",
    "优青",
    "职级",
    "登录",
    "搜索",
    "毕业",
    "留影",
    "政策",
    "文件",
    "规章",
    "制度",
    "学员",
    "心声",
    "在线",
    "办公",
    "博士生",
    "旧版",
    "网站",
    "理论",
    "武装",
    "力量",
    "研究",
    "机构",
    "中心",
    "基地",
    "服务",
    "合作",
    "招生",
    "招聘",
    "学生",
    "校友",
    "下载",
    "工作",
    "委员会",
    "体系",
    "架构",
    "寄语",
    "概况",
    "简介",
    "大事",
    "专著",
    "联系",
    "我们",
    "奖励",
    "荣誉",
    "历史",
    "沿革",
    "办事",
    "指南",
    "公示",
    "国际化",
    "博士后",
    "行政",
    "系列",
    "退休",
    "人才",
)
_UNIT_TEXT_RE = re.compile(
    r"(学院|学系|工程系|科学系|文学系|研究院|研究中心|教学中心|体育部|书院|实验室|"
    r"School|Department|Institute|Center)",
    re.IGNORECASE,
)
_FACULTY_LIST_TEXT_RE = re.compile(
    r"(师资|教师|教授|导师|人员|Faculty|People|Staff|Team|Members|队伍|在职教师|教师名录)",
    re.IGNORECASE,
)
_NON_FACULTY_LIST_TEXT_RE = re.compile(
    r"(新闻|通知|公告|报告|讲座|论坛|会议|活动|招聘|培训|出版|进展|团队|课题组|"
    r"公示|应邀|主讲|岗位|成功举办|最新|午餐会|预告|举报|学术报告|研究进展|"
    r"受聘|委员|剖析|校外兼职|深度|现象|机制|"
    r"教授观点|教师事务|优秀提案|班主任|辅导员|素材形成|论文获|荣获|喜讯|"
    r"教授接待日|访问交流|社会服务|专业之力|新篇章|乡村振兴|"
    r"Nature|Science|NC|20\d{2}|[0-9]{2,}|[：:|])",
    re.IGNORECASE,
)
_FACULTY_LIST_PAGINATION_TEXT_RE = re.compile(r"(下一页|尾页|末页|Next)", re.IGNORECASE)
_FACULTY_LIST_PAGINATION_URL_RE = re.compile(r"/[^/]*list\d+\.htm$", re.IGNORECASE)
_NON_UNIT_TEXT_RE = re.compile(
    r"(招生|招聘|邮箱|图书馆|校友|捐赠|内网|English|课程|职业发展|新闻|通知|公告|"
    r"Admissions|Jobs|Library|Alumni|Donate)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DiscoveredSource:
    id: str
    url: str
    type: str
    department: str | None
    status: str
    notes: str
    discovered_from: str
    anchor_text: str


def discover_tsinghua_profiles_from_cache(
    cache_root: str | Path,
    *,
    allowed_domains: list[str] | None = None,
) -> list[DiscoveredSource]:
    return discover_profiles_from_cache(
        cache_root,
        university_name_zh="清华大学",
        source_id_prefix="thu-profile",
        allowed_domains=allowed_domains or ["tsinghua.edu.cn", "*.tsinghua.edu.cn"],
    )


def discover_profiles_from_cache(
    cache_root: str | Path,
    *,
    university_name_zh: str,
    source_id_prefix: str,
    allowed_domains: list[str],
) -> list[DiscoveredSource]:
    store = CacheStore(cache_root)
    discovered: dict[str, DiscoveredSource] = {}
    for record in store.iter_records():
        if record.university != university_name_zh:
            continue
        if not record.text_cache_path or not record.cache_path:
            continue
        html_path = Path(record.cache_path)
        if not html_path.exists():
            continue
        html = html_path.read_text(encoding=record.encoding or "utf-8", errors="replace")
        for url, anchor_text in _candidate_profile_links(record, html, allowed_domains):
            if url in discovered:
                continue
            discovered[url] = DiscoveredSource(
                id=_source_id(url, prefix=source_id_prefix),
                url=url,
                type="teacher_profile",
                department=record.department,
                status="discovered",
                notes=f"Discovered from {record.source_type} page.",
                discovered_from=record.source_url,
                anchor_text=anchor_text,
            )
    return sorted(discovered.values(), key=lambda item: item.url)


def discover_tsinghua_units_from_cache(
    cache_root: str | Path,
    *,
    allowed_domains: list[str] | None = None,
) -> list[DiscoveredSource]:
    return discover_units_from_cache(
        cache_root,
        university_name_zh="清华大学",
        source_id_prefix="thu-unit",
        allowed_domains=allowed_domains or ["tsinghua.edu.cn", "*.tsinghua.edu.cn"],
    )


def discover_units_from_cache(
    cache_root: str | Path,
    *,
    university_name_zh: str,
    source_id_prefix: str,
    allowed_domains: list[str],
) -> list[DiscoveredSource]:
    store = CacheStore(cache_root)
    discovered: dict[str, DiscoveredSource] = {}
    for record in store.iter_records():
        if record.university != university_name_zh:
            continue
        if record.source_type != "unit_index" or not record.cache_path:
            continue
        html_path = Path(record.cache_path)
        if not html_path.exists():
            continue
        html = html_path.read_text(encoding=record.encoding or "utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.find_all("a", href=True):
            text = _clean_anchor_text(anchor.get_text(" ", strip=True))
            if not _looks_like_unit_text(text):
                continue
            url = normalize_url(urljoin(record.final_url or record.source_url, anchor["href"].strip()))
            host = urlsplit(url).hostname or ""
            if not host_matches(host, allowed_domains):
                continue
            if url in discovered:
                continue
            discovered[url] = DiscoveredSource(
                id=_source_id(url, prefix=source_id_prefix),
                url=url,
                type="unit_home",
                department=text,
                status="discovered",
                notes="Discovered from Tsinghua unit index page.",
                discovered_from=record.source_url,
                anchor_text=text,
            )
    return sorted(discovered.values(), key=lambda item: item.url)


def discover_tsinghua_faculty_lists_from_cache(
    cache_root: str | Path,
    *,
    allowed_domains: list[str] | None = None,
) -> list[DiscoveredSource]:
    return discover_faculty_lists_from_cache(
        cache_root,
        university_name_zh="清华大学",
        source_id_prefix="thu-faculty-list",
        allowed_domains=allowed_domains or ["tsinghua.edu.cn", "*.tsinghua.edu.cn"],
    )


def discover_faculty_lists_from_cache(
    cache_root: str | Path,
    *,
    university_name_zh: str,
    source_id_prefix: str,
    allowed_domains: list[str],
) -> list[DiscoveredSource]:
    store = CacheStore(cache_root)
    discovered: dict[str, DiscoveredSource] = {}
    for record in store.iter_records():
        if record.university != university_name_zh:
            continue
        if record.source_type not in {"unit_home", "faculty_portal", "unit_index", "faculty_list"}:
            continue
        if not record.cache_path:
            continue
        html_path = Path(record.cache_path)
        if not html_path.exists():
            continue
        html = html_path.read_text(encoding=record.encoding or "utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.find_all("a", href=True):
            text = _clean_anchor_text(anchor.get_text(" ", strip=True))
            url = normalize_url(urljoin(record.final_url or record.source_url, anchor["href"].strip()))
            is_faculty_list = _looks_like_faculty_list_text(text)
            is_pagination = record.source_type == "faculty_list" and _looks_like_faculty_list_pagination(
                text, url
            )
            if not is_faculty_list and not is_pagination:
                continue
            host = urlsplit(url).hostname or ""
            if not host_matches(host, allowed_domains):
                continue
            if url in discovered:
                continue
            discovered[url] = DiscoveredSource(
                id=_source_id(url, prefix=source_id_prefix),
                url=url,
                type="faculty_list",
                department=record.department,
                status="discovered",
                notes=f"Discovered from {record.source_type} page.",
                discovered_from=record.source_url,
                anchor_text=text,
            )
    return sorted(discovered.values(), key=lambda item: item.url)


def write_discovered_sources_yaml(
    sources: list[DiscoveredSource],
    path: str | Path,
    *,
    university_id: str = "thu",
    university_name_zh: str = "清华大学",
    university_name_en: str = "Tsinghua University",
    allowed_domains: list[str] | None = None,
) -> None:
    allowed_domains = allowed_domains or ["tsinghua.edu.cn", "*.tsinghua.edu.cn"]
    data = {
        "version": 1,
        "universities": [
            {
                "id": university_id,
                "name_zh": university_name_zh,
                "name_en": university_name_en,
                "allowed_domains": allowed_domains,
                "entries": [
                    {
                        "id": source.id,
                        "url": source.url,
                        "type": source.type,
                        "department": source.department,
                        "name_hint": source.anchor_text if source.type == "teacher_profile" else None,
                        "status": source.status,
                        "notes": (
                            f"{source.notes} anchor={source.anchor_text!r}; "
                            f"from={source.discovered_from}"
                        ),
                    }
                    for source in sources
                ],
            }
        ],
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _candidate_profile_links(
    record: CacheRecord,
    html: str,
    allowed_domains: list[str],
) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str]] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if href.startswith(("javascript:", "mailto:", "#")):
            continue
        url = normalize_url(urljoin(record.final_url or record.source_url, href))
        host = urlsplit(url).hostname or ""
        if not host_matches(host, allowed_domains):
            continue
        if _looks_like_non_profile_url(url):
            continue
        text = _clean_anchor_text(anchor.get_text(" ", strip=True))
        if _looks_like_profile_url(url):
            candidates.append((url, _name_hint_from_anchor(text) or ""))
            continue
        if record.source_type in {"faculty_list", "profile_index", "profile_portal"} and (
            _looks_like_faculty_detail_link(url, text)
            or (_looks_like_name_anchor(text) and _looks_like_html_page(url))
        ):
            candidates.append((url, _name_hint_from_anchor(text) or text))
    return candidates


def _looks_like_profile_url(url: str) -> bool:
    path = urlsplit(url).path
    return bool(_PROFILE_PATH_RE.search(path))


def _looks_like_non_profile_url(url: str) -> bool:
    return bool(_NON_PROFILE_URL_RE.search(url))


def _looks_like_faculty_detail_link(url: str, anchor_text: str) -> bool:
    path = urlsplit(url).path
    if not (
        re.search(r"/info/\d+/\d+\.htm$", path)
        or _WEBPLUS_PROFILE_PAGE_RE.search(path)
    ):
        return False
    return bool(_name_hint_from_anchor(anchor_text))


def _name_hint_from_anchor(anchor_text: str) -> str | None:
    text = _clean_anchor_text(anchor_text)
    text = re.sub(r"[（(].*?[)）]", "", text)
    text = re.sub(r"\s+", "", text)
    repeat_match = re.match(r"^([\u4e00-\u9fff·]{2,4})\1", text)
    if repeat_match and _looks_like_name_anchor(repeat_match.group(1)):
        return repeat_match.group(1)
    title_match = re.match(
        r"^([\u4e00-\u9fff·]{2,4})(?:教授|副教授|研究员|副研究员|讲师|助理教授|"
        r"助理研究员|博士生导师|硕士生导师)",
        text,
    )
    if title_match and _looks_like_name_anchor(title_match.group(1)):
        return title_match.group(1)
    return text if _looks_like_name_anchor(text) else None


def _looks_like_name_anchor(anchor_text: str) -> bool:
    return bool(
        _ZH_NAME_RE.fullmatch(anchor_text)
        and anchor_text not in _NON_NAME_ANCHORS
        and not any(token in anchor_text for token in _NON_NAME_SUBSTRINGS)
        and not anchor_text.lower().startswith(("http://", "https://"))
    )


def _looks_like_html_page(url: str) -> bool:
    split = urlsplit(url)
    path = split.path
    if _HTML_PAGE_RE.search(path):
        return True
    suffix = Path(path).suffix.lower()
    return not suffix and path.rstrip("/").count("/") >= 1


def _clean_anchor_text(text: str) -> str:
    cleaned = " ".join(text.replace("\ufeff", "").split())
    return cleaned.strip(" >›»·•-*　")


def _looks_like_unit_text(text: str) -> bool:
    if not text or _NON_UNIT_TEXT_RE.search(text):
        return False
    return bool(_UNIT_TEXT_RE.search(text))


def _looks_like_faculty_list_text(text: str) -> bool:
    if not text or len(text) > 60:
        return False
    if _NON_FACULTY_LIST_TEXT_RE.search(text):
        return False
    return bool(_FACULTY_LIST_TEXT_RE.search(text))


def _looks_like_faculty_list_pagination(text: str, url: str) -> bool:
    return bool(
        text
        and _FACULTY_LIST_PAGINATION_TEXT_RE.search(text)
        and _FACULTY_LIST_PAGINATION_URL_RE.search(urlsplit(url).path)
    )


def _source_id(url: str, *, prefix: str = "thu-profile") -> str:
    split = urlsplit(url)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", f"{split.netloc}{split.path}").strip("-").lower()
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}-{slug[:72]}-{digest}"
