from datetime import datetime

from data.plugins.astrbot_plugin_glimpse.markers import parse_markers
from data.plugins.astrbot_plugin_glimpse.prompts import (
    DEFAULT_GUIDE,
    build_guide,
    build_prompt,
)

DAY, NIGHT = datetime(2026, 10, 31, 10), datetime(2026, 10, 31, 22)


def test_photo_prompt_rules():
    p = build_prompt(parse_markers("[📷拍照：阳台上的小鸟]")[0], [], DAY)
    assert "阳台上的小鸟" in p
    for phrase in ("smartphone", "first-person", "no human faces", "no hands", "daytime"):
        assert phrase in p
    assert "same room" not in p


def test_night_and_refs():
    p = build_prompt(parse_markers("[📷拍照·公寓-露台：吊椅]")[0], [("scene", "公寓-露台")], NIGHT)
    assert "night" in p and "same room" in p and "different angle" in p


def test_film_prompt():
    p = build_prompt(parse_markers("[🎞️胶片：海]")[0], [], DAY)
    assert "film" in p and "no hands" in p


def test_doodle_prompt():
    p = build_prompt(parse_markers("[✏️涂鸦：钓鱼]")[0], [], DAY)
    for phrase in ("doodle", "ballpoint", "colored pencil", "white paper", "silver", "fang", "no text"):
        assert phrase in p
    assert "smartphone" not in p and "main subject" not in p


def test_guide():
    g = build_guide(DEFAULT_GUIDE, ["公寓-客厅", "邱诺亚的花店"], ["芝士", "蛋挞"], "便服-灰色卫衣", False)
    assert "公寓（客厅）、邱诺亚的花店" in g
    assert "[📷拍照" in g and "[✏️涂鸦" in g and "[📷分享图片" in g


def test_guide_no_scenes():
    assert "（暂无）" in build_guide(DEFAULT_GUIDE, [], [], "", False)
    assert build_guide("{x} {scenes}", ["a"], [], "", False) == "{x} a"


def test_photo_prompt_avoids_cg_look():
    p = build_prompt(parse_markers("[📷拍照：猫]")[0], [], NIGHT)
    for phrase in ("unedited", "not a CG render", "no cinematic lighting", "sensor noise"):
        assert phrase in p


def test_refs_only_for_layout():
    p = build_prompt(parse_markers("[📷拍照·公寓-客厅：猫]")[0], [("scene", "公寓-客厅")], DAY)
    assert "layout" in p and "do not copy their rendering style" in p


def test_cinematic_style_uses_previous_look():
    m = parse_markers("[📷拍照·公寓-客厅：猫]")[0]
    p = build_prompt(m, [("scene", "公寓-客厅")], NIGHT, cinematic=True)
    assert "Authentic everyday snapshot" in p and "warm indoor lamps" in p
    assert "unedited" not in p and "do not copy their rendering style" not in p
    assert "no human faces" in p and "same room" in p


def test_default_style_is_realistic():
    p = build_prompt(parse_markers("[📷拍照：猫]")[0], [], DAY)
    assert "unedited" in p


def test_guide_objects_outfit_and_hands():
    g = build_guide(DEFAULT_GUIDE, [], ["芝士", "蛋挞"], "便服-灰色卫衣", False)
    assert "芝士、蛋挞" in g and "便服-灰色卫衣" in g and "也不会出现你的手" in g
    g = build_guide(DEFAULT_GUIDE, [], [], "", True)
    assert "（暂无）" in g and "（未设置）" in g and "自己的手" in g


def test_season_in_photo_not_doodle():
    autumn = datetime(2026, 10, 31, 10)
    assert "Season: autumn" in build_prompt(parse_markers("[📷拍照：猫]")[0], [], autumn)
    assert "Season: winter" in build_prompt(parse_markers("[🎞️胶片：雪]")[0], [], datetime(2026, 1, 5, 10))
    assert "Season" not in build_prompt(parse_markers("[✏️涂鸦：猫]")[0], [], autumn)


def test_reference_labels_in_order():
    refs = [("object", "芝士"), ("outfit", "便服-灰色卫衣"), ("hand", ""), ("scene", "公寓-客厅")]
    p = build_prompt(parse_markers("[📷拍照·公寓-客厅：芝士]")[0], refs, DAY, show_hands=True)
    assert p.index("Reference image 1: 芝士") < p.index("Reference image 2") < p.index("Reference image 4")
    assert "exact appearance" in p and "same room" in p


def test_show_hands_relaxes_rule_but_never_face():
    m = parse_markers("[📷拍照：我手里捏着糖炒栗子]")[0]
    p = build_prompt(m, [], DAY, show_hands=True, outfit="睡衣-条纹")
    assert "no hands," not in p and "no human faces" in p and "his own hand" in p
    assert "holding or touching" in p and "睡衣-条纹" in p and "short-sleeved" in p
    assert "no hands" in build_prompt(m, [], DAY)


def test_doodle_is_flat_scan_not_photo():
    p = build_prompt(parse_markers("[✏️涂鸦：钓鱼]")[0], [], DAY)
    for phrase in ("flat scan", "not a photo of paper", "lots of empty white space"):
        assert phrase in p


def test_photo_uses_phone_optics_and_neutral_color():
    p = build_prompt(parse_markers("[📷拍照：落叶]")[0], [], DAY)
    for phrase in ("wide-angle", "deep depth of field", "neutral white balance", "no warm filter"):
        assert phrase in p


def test_free_scene_defaults_to_east_asian_city():
    free = build_prompt(parse_markers("[📷拍照：街边的梧桐]")[0], [], DAY)
    fixed = build_prompt(
        parse_markers("[📷拍照·临空街道：落叶]")[0], [("scene", "临空街道")], DAY
    )
    assert "modern East Asian city" in free and "modern East Asian city" not in fixed


def test_hands_note_describes_masculine_hands():
    p = build_prompt(parse_markers("[📷拍照：我手里的咖啡]")[0], [], DAY, show_hands=True)
    assert "defined knuckles" in p and "short clean nails" in p


def test_guide_encourages_sharing_and_plain_wording():
    g = build_guide(DEFAULT_GUIDE, [], [], "", False)
    assert "分享欲" in g and "平实" in g


def test_guide_groups_scenes_by_place():
    g = build_guide(
        DEFAULT_GUIDE, ["公寓-卧室", "公寓-客厅", "列车", "猎人协会-工位"], [], "", False
    )
    assert "公寓（卧室/客厅）、列车、猎人协会（工位）" in g


def test_guide_selfie_rule_and_wardrobe():
    g = build_guide(DEFAULT_GUIDE, [], [], "便服-卫衣", False, ["便服-卫衣", "便服-衬衫"])
    assert "头发" in g and "对着镜子" in g and "[👕换装：" in g
    assert "便服-卫衣、便服-衬衫" in g
    assert "（无）" in build_guide(DEFAULT_GUIDE, [], [], "", False)


def test_photo_prompt_hides_hair_and_shoulders():
    p = build_prompt(parse_markers("[📷拍照：猫]")[0], [], DAY)
    assert "no hair" in p and "no shoulders" in p


def test_prompt_overrides_and_blank_fallback():
    m = parse_markers("[📷拍照：猫]")[0]
    p = build_prompt(m, [], DAY, prompts={"photo_template": "CUSTOM", "day_light": ""})
    assert p.startswith("CUSTOM") and "Lighting: daytime" in p
    g = build_guide("{hands}", [], [], "", True, prompts={"guide_hands_on": "可以露手"})
    assert g == "可以露手"


def test_hands_note_overrides_template_rule():
    p = build_prompt(parse_markers("[📷拍照：我手里的咖啡]")[0], [], DAY, show_hands=True)
    assert "overrides any earlier" in p


def test_film_looks_like_real_negative():
    p = build_prompt(parse_markers("[🎞️胶片：街道]")[0], [], DAY)
    assert "scanned 35mm negative" in p and "no golden cast" in p
    assert "light leak at one edge" not in p and "not a CG render" in p


def test_main_subject_is_focus():
    for text in ("[📷拍照：猫]", "[🎞️胶片：猫]"):
        assert "main subject" in build_prompt(parse_markers(text)[0], [], DAY)


def test_scene_refs_lock_architecture():
    refs = [("scene", "公寓-厨房")]
    p = build_prompt(parse_markers("[📷拍照·公寓-厨房：猫]")[0], refs, DAY)
    assert "never add a window" in p


def test_guide_asks_subject_first():
    g = build_guide(DEFAULT_GUIDE, [], [], "", False)
    assert "先写拍的是什么" in g and "不要额外编" not in g


def test_room_notes_in_prompt():
    m = parse_markers("[📷拍照·公寓-厨房：猫]")[0]
    p = build_prompt(m, [("scene", "公寓-厨房")], DAY, room_notes="没有窗户")
    assert "Room facts" in p and "没有窗户" in p
    assert "Room facts" not in build_prompt(m, [("scene", "公寓-厨房")], DAY)
