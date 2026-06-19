from advisors.registry import load_registry, registry_from_dict


def test_sources_registry_is_valid() -> None:
    registry = load_registry("configs/sources.yaml")
    assert registry.validate() == []
    assert {university.id for university in registry.universities} == {"thu", "pku"}
    assert len(registry.entries) >= 2


def test_source_registry_reads_name_hint_from_notes() -> None:
    registry = registry_from_dict(
        {
            "version": 1,
            "universities": [
                {
                    "id": "thu",
                    "name_zh": "清华大学",
                    "name_en": "Tsinghua University",
                    "allowed_domains": ["*.tsinghua.edu.cn"],
                    "entries": [
                        {
                            "id": "profile-1",
                            "url": "https://www.cs.tsinghua.edu.cn/info/1111/3490.htm",
                            "type": "teacher_profile",
                            "notes": "Discovered from faculty_list page. anchor='冯建华'; from=x",
                        }
                    ],
                }
            ],
        }
    )

    assert registry.entries[0].name_hint == "冯建华"
