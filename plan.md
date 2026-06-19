# Advisors Project Plan

## 项目定位

本项目建设一个以高校官网教师主页为核心来源的中国高校教师公开事实数据集。项目优先保证数据来源公开、可追溯、可复现、可增量更新，而不是在早期追求全量学术成果图谱。

核心产物是版本化的 Parquet 开放数据包。教师主页缓存是基础事实信息源之一，用于复核、增量更新和重新抽取结构化数据。

## 第一阶段范围

v0.1 聚焦：

- 清华大学
- 北京大学
- C9 高校：复旦大学、上海交通大学、南京大学、浙江大学、中国科学技术大学、哈尔滨工业大学、西安交通大学
- 尽量采集上述高校所有公开教师主页，并用覆盖率台账说明“尽量”的口径
- 只使用高校官网、院系官网、实验室官网、官方教师主页系统等学校官方公开页面
- 暂不接入 OpenAlex、CNKI、万方、维普、专利库、基金委外部查询库等第三方来源

后续扩展顺序：

1. 985 高校
2. 211 高校
3. 其他高校

## 数据原则

- 所有数据必须来自公开网页。
- 每条记录必须保留来源 URL 和采集时间。
- 每条记录应尽量保留解析方式、页面 hash 或其他可复核信息。
- 教师主页需要维护缓存。缓存记录原始页面或等价的可复核页面内容，是后续结构化抽取的事实来源之一。
- 覆盖率必须可解释，不能只给最终人数。
- 不做主观评价，不做导师优劣、学术水平、推荐分等非事实字段。
- 合作网络、影响力网络、师承网络等属于后续生成数据，不作为第一阶段事实数据。

## 隐私与排除规则

永不入库：

- 手机号
- 固定电话、办公室电话、传真等任何电话号码
- 身份证号
- 护照号、证件号等私人证件信息
- 家庭住址

可以入库，但必须来自高校官网公开页面：

- 出生日期
- 电子邮箱
- 办公地址
- 职称
- 所属高校、院系、实验室或课题组
- 研究方向
- 个人主页 URL
- 教育经历、工作经历、社会兼职等公开简介信息

## 第一阶段数据内容

教师实体暂不定死完整 schema。已确认的核心字段包括：

- 姓名
- 英文名/拼音名，可能有多个
- 所属高校
- 院系/实验室
- 职称
- 个人主页 URL
- 数据来源
- 数据更新时间或采集时间

论文、专利、基金、荣誉等成果信息暂不强制结构化。若教师官网主页中公开列出相关内容，第一阶段以文本段落形式保存。

基金信息只从高校官网教师主页中抽取，不额外查询外部基金数据库。

## 建议数据表

核心 Parquet 输出可以从以下表开始，后续允许演化：

### teachers.parquet

- profile_id
- person_id
- person_id_status
- identity_confidence
- name
- university
- department
- lab_or_group
- title
- homepage_url
- source_url
- fetched_at
- page_updated_at
- source_hash

### teacher_names.parquet

- profile_id
- name_value
- name_type
- source_url
- fetched_at

### teacher_attributes.parquet

- profile_id
- attr_key
- attr_value
- source_url
- fetched_at
- confidence
- extractor

适合存放邮箱、办公地址、出生日期、导师类型、教育经历、工作经历等尚未固定 schema 的公开属性。

### teacher_sections.parquet

- profile_id
- section_type
- section_title
- section_text
- source_url
- fetched_at

适合存放研究方向、个人简介、项目/基金、论文文本、专利文本、荣誉文本等非结构化或半结构化内容。

### source_pages.parquet

- source_url
- university
- department
- fetched_at
- status_code
- cache_key
- cache_path
- content_hash
- text_hash
- parser_name
- parser_version

## 教师主页缓存

教师主页缓存是项目的基础事实层。采集流程应先缓存页面，再从缓存中抽取结构化数据。

目录布局：

- `data/cache/<school>/` 存放该校缓存页面、正文缓存和 metadata。
- `data/working/<school>/` 存放该校发现 registry、中间抽取表、质量报告和 release。
- `data/working/<school>/release-<school>-v0.1.0/` 存放该校公开 Parquet release。
- 跨校汇总文件保留在 `data/working/` 根目录。

缓存目标：

- 支持重复解析，避免每次结构化抽取都重新访问官网。
- 支持页面变更检测和增量更新。
- 支持数据质量审计，确保结构化结果可追溯。
- 支持后续改进解析器后重新抽取历史页面。

建议缓存内容：

- 规范化后的 source_url
- fetched_at
- HTTP 状态码和响应头摘要
- content_hash
- 原始 HTML 或等价页面内容的本地路径
- 从页面抽取出的正文文本缓存路径
- 页面编码、content_type、最终跳转 URL

缓存注意事项：

- 缓存可以包含官网原始页面中出现但不进入公开数据表的信息，例如电话号码。
- 电话号码、身份证号等排除字段不得进入 Parquet 公开输出表。
- 原始 HTML 缓存默认不作为公开 release 的一部分，除非后续单独评估版权、隐私和体积策略。
- 缓存目录默认不进入 git。
- 公开 release 默认只包含结构化 Parquet、manifest、说明文档和必要的质量报告，不包含原始 HTML 缓存。
- 结构化抽取必须从缓存读取，不能把在线网页抓取和字段解析耦合在同一步里。

## ID 策略

- profile_id：页面级 ID，优先基于规范化后的 homepage_url 生成。它代表一个公开主页或信息页。
- person_id：人级 ID，后续用于跨页面融合。v0.1 可以先基于 university + name + department 生成，并标记为暂定结果。
- person_id_status：说明 person_id 的状态。v0.1 默认可用 tentative，后续可演化为 reviewed、merged、split、deprecated 等。
- identity_confidence：记录人员融合置信度。v0.1 可先使用低粒度等级或数值，不应被理解为身份真实性评价。

页面事实和人员融合结果需要区分。一个教师可能出现在院系页、实验室页、教师主页系统页等多个页面中。

## 官方来源边界

v0.1 只采集白名单官方来源：

- 学校主域名及其二级域名。
- 院系、实验室、研究中心等学校组织维护的官方站点。
- 学校官方教师主页系统、机构主页系统、院系师资页面。
- 官方页面内链接到的教师详情页，如果仍在白名单官方域名内，可以采集。

外跳链接处理：

- 教师个人自建站、商业平台、GitHub、Google Scholar、ResearchGate、LinkedIn 等外部站点不采集正文。
- 外跳个人主页 URL 可以作为官网页面中出现的公开链接记录，但不得作为 v0.1 的事实抽取来源。
- 对是否官方存在疑问的域名，先进入待审核 source registry，不直接抓取。

## 采集策略

- 使用人工维护的 source registry 记录学校、允许域名、入口 URL、院系入口页、采集备注。
- 爬虫只在白名单官方域名内运行。
- 优先发现包含师资、教师、faculty、people、staff、教授、副教授、讲师等特征的页面。
- 对清华、北大的重点站点编写轻量 adapter，避免过早设计过度通用爬虫。
- 采集时保留 URL、采集时间、页面 hash、解析器版本。
- 采集流程分为两步：先写入教师主页缓存，再从缓存抽取结构化数据。
- 不公开原始 HTML 缓存，除非后续明确评估版权、隐私和存储策略。

## 覆盖率台账

v0.1 需要维护覆盖率台账，用来说明采集范围和缺口。

建议记录：

- university
- school_or_department
- source_entry_url
- source_entry_type
- allowed_domain
- discovered_list_pages
- visited_list_pages
- discovered_profile_pages
- cached_profile_pages
- parsed_profile_pages
- failed_pages
- failure_reason
- reviewed_at

覆盖率报告至少包含：

- 已发现院系/单位入口数量。
- 已访问教师列表页数量。
- 已发现教师主页数量。
- 成功缓存主页数量。
- 成功解析主页数量。
- 失败页面数量和主要失败原因。
- 尚未覆盖或待人工确认的院系/入口。

## 爬取礼仪与合规

- 遵守 robots.txt 和站点公开访问限制。
- 使用清晰、克制的 User-Agent，标明项目用途和联系入口。
- 设置请求限速，避免对学校官网造成压力。
- 设置重试上限和退避策略，不无限重试。
- 不绕过登录、验证码、IP 限制、访问控制或反爬措施。
- 不采集需要认证后才能访问的内容。
- 对异常响应、跳转、下载文件和非 HTML 内容做显式记录。

## 结构化抽取协作方式

从事实信息抓取到结构化数据的流程总是开启 subagent 完成。主流程负责确定范围、缓存策略、输出 schema 和质量标准；subagent 负责执行或审查从缓存页面到结构化记录的抽取、字段清洗、排除字段检查和质量报告。

适用范围包括：

- 从教师主页缓存抽取 teachers、teacher_names、teacher_attributes、teacher_sections。
- 从缓存文本中识别研究方向、邮箱、办公地址、职称、院系、项目/基金文本等字段。
- 检查电话号码、证件号、家庭住址等排除字段是否进入结构化输出。
- 生成字段缺失率、重复候选、解析失败页面等质量报告。

## v0.1 完成标准

- 有清华、北大、C9 高校的 source registry。
- 有覆盖率台账，说明已覆盖入口、已发现教师页、成功缓存页、成功解析页和失败原因。
- 尽量覆盖清华、北大、C9 高校主要官方教师主页入口和院系教师列表。
- 生成可复现的 Parquet 数据包。
- 每个 release 包含 manifest。
- 每条教师记录可追溯到来源 URL。
- 教师主页缓存可复用，结构化数据可从缓存重新生成。
- 电话号码不会进入任何输出表。
- 官网主页中的基金、项目、论文、专利、荣誉等内容可以作为文本段落保留。
- 输出基础数据质量报告，包括总人数、院系分布、缺字段率、重复候选、邮箱数量、来源页面数量。

## Release Manifest

每个公开数据包应包含 manifest 文件，建议命名为 `manifest.json`。

manifest 至少记录：

- dataset_name
- dataset_version
- schema_version
- generated_at
- source_commit
- universities
- release_files
- row_counts
- source_page_count
- cache_batch_id
- parser_versions
- coverage_report_path
- quality_report_path
- license
- notes

## 暂不做

- 不接第三方论文数据库。
- 不接外部专利数据库。
- 不接外部基金数据库。
- 不生成合作网络。
- 不做教师评价、推荐、排名。
- 不把论文、专利、基金、荣誉强制结构化为独立事实实体。
