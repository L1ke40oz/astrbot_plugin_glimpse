import pytest

from data.plugins.astrbot_plugin_glimpse.markers import (
    looks_like_marker,
    fallback_text,
    parse_markers,
    parse_outfit_changes,
)


def test_photo_with_scene():
    text = "刚回家$[📷拍照·公寓-露台：吊椅上睡着一只橘猫，星星灯刚亮]$你看"
    [m] = parse_markers(text)
    assert (m.kind, m.scene, m.description) == (
        "photo",
        "公寓-露台",
        "吊椅上睡着一只橘猫，星星灯刚亮",
    )
    assert text[m.start : m.end] == "[📷拍照·公寓-露台：吊椅上睡着一只橘猫，星星灯刚亮]"


def test_loose_variants():
    assert parse_markers("[拍照:海边的落日]")[0].kind == "photo"
    assert parse_markers("[📷照片：猫]")[0].kind == "photo"
    assert parse_markers("[🎞️胶片-邱诺亚的花店：门口的风铃]")[0].scene == "邱诺亚的花店"
    assert (
        parse_markers("[ ✏️ 涂鸦 ： 钓到一条鱼（并没有） ]")[0].description
        == "钓到一条鱼（并没有）"
    )


def test_doodle_scene_ignored():
    assert parse_markers("[✏️涂鸦·公寓-客厅：我在睡觉]")[0].scene == ""


def test_ignores_share_marker():
    assert parse_markers("[📷分享图片：我今天的样子] [💭状态：正在看日落]") == []


def test_multiple_in_order():
    ms = parse_markers("[📷拍照：a]中间[✏️涂鸦：b]")
    assert [m.kind for m in ms] == ["photo", "doodle"]


def test_fallback_text():
    [p, f, d] = parse_markers("[📷拍照·公寓-厨房：泡面][🎞️胶片：海][✏️涂鸦：兔子]")
    assert fallback_text(p) == "[📷分享图片：泡面]"
    assert fallback_text(f) == "[📷分享图片：海]"
    assert fallback_text(d) == "[✏️涂鸦：兔子]"


def test_scene_separators_normalized():
    assert parse_markers("[📷拍照·公寓·客厅：猫]")[0].scene == "公寓-客厅"
    assert parse_markers("[📷拍照·公寓—露台：猫]")[0].scene == "公寓-露台"


def test_parse_outfit_changes():
    text = "等我一下[👕换装：便服-白衬衫]$换好了"
    [(start, end, name)] = parse_outfit_changes(text)
    assert name == "便服-白衬衫" and text[start:end] == "[👕换装：便服-白衬衫]"
    assert parse_outfit_changes("[换装: 睡衣-格子睡衣 ]")[0][2] == "睡衣-格子睡衣"
    assert parse_outfit_changes("[📷拍照：衣柜]") == []


def test_chinese_dashes_in_scene():
    assert parse_markers("[📷拍照·公寓——客厅：猫]")[0].scene == "公寓-客厅"
    assert parse_markers("[📷拍照——公寓-客厅：猫]")[0].scene == "公寓-客厅"


@pytest.mark.parametrize(
    "text",
    [
        "[📷拍照⋅公寓−厨房：锅]",
        "[📷拍照•公寓–厨房：锅]",
        "[📷拍照・公寓－厨房：锅]",
        "[📷拍照 公寓-厨房：锅]",
        "[📷拍照‧公寓‐厨房：锅]",
        "[📷拍照·公寓——厨房：锅]",
    ],
)
def test_unusual_separators(text):
    [m] = parse_markers(text)
    assert (m.kind, m.scene, m.description) == ("photo", "公寓-厨房", "锅")


def test_looks_like_marker():
    assert looks_like_marker("[📷拍照/公寓：锅]")
    assert not looks_like_marker("今天拍照了吗")
    assert not looks_like_marker("[📷分享图片：猫]")
