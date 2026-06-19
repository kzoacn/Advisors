from advisors.xjtu_portal import parse_tsites_load_data_options


def test_parse_tsites_load_data_options() -> None:
    html = """
    <script>
    var tsites_load_data_options = {"viewUniqueId":1095185,"showlang":"zh_CN",
    "viewId":1095185,"siteOwner":2105667170,"pageNumber":16,"profilelen":1000,
    "ellipsis":"...","ispreview":false,"viewMode":8};
    </script>
    """

    options = parse_tsites_load_data_options(html)

    assert options is not None
    assert options["viewUniqueId"] == 1095185
    assert options["siteOwner"] == 2105667170
    assert options["showlang"] == "zh_CN"
