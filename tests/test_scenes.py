from datetime import datetime

import pytest

from data.plugins.astrbot_plugin_glimpse.scenes import (
    first_image,
    list_scenes,
    match_objects,
    next_category_change,
    outfit_category,
    pick_outfit,
    pick_refs,
    scene_notes,
    wardrobe,
)

DAY, NIGHT = datetime(2026, 10, 31, 10), datetime(2026, 10, 31, 22)


@pytest.fixture
def scene_root(tmp_path):
    files = {
        "公寓-客厅": ["白天.jpg", "夜晚.jpg", "客厅全景.jpg"],
        "公寓-卧室": ["夜晚.jpg"],
        "公寓-厨房": ["厨房.jpg", "notes.txt"],
        "空文件夹": [],
    }
    for folder, names in files.items():
        (tmp_path / folder).mkdir()
        for name in names:
            (tmp_path / folder / name).write_bytes(b"x")
    return tmp_path


def test_list_scenes(scene_root):
    assert list_scenes(scene_root) == ["公寓-卧室", "公寓-厨房", "公寓-客厅"]


def test_missing_scene_dir(tmp_path):
    assert list_scenes(tmp_path / "nope") == []
    assert pick_refs(tmp_path / "nope", "公寓-客厅", DAY, 3) == []


def test_time_tagged_first_then_untagged(scene_root):
    assert [p.name for p in pick_refs(scene_root, "公寓-客厅", DAY, 3)] == [
        "白天.jpg",
        "客厅全景.jpg",
    ]
    assert [p.name for p in pick_refs(scene_root, "公寓-客厅", NIGHT, 3)] == [
        "夜晚.jpg",
        "客厅全景.jpg",
    ]


def test_max_refs_one(scene_root):
    assert [p.name for p in pick_refs(scene_root, "公寓-客厅", DAY, 1)] == ["白天.jpg"]


def test_no_match_uses_all(scene_root):
    assert [p.name for p in pick_refs(scene_root, "公寓-卧室", DAY, 3)] == ["夜晚.jpg"]


def test_unknown_scene_and_non_images(scene_root):
    assert pick_refs(scene_root, "不存在", DAY, 3) == []
    assert [p.name for p in pick_refs(scene_root, "公寓-厨房", DAY, 3)] == ["厨房.jpg"]


def test_boundary_hours(scene_root):
    assert pick_refs(scene_root, "公寓-客厅", datetime(2026, 1, 1, 6), 1)[0].name == "白天.jpg"
    assert pick_refs(scene_root, "公寓-客厅", datetime(2026, 1, 1, 18), 1)[0].name == "夜晚.jpg"


def test_scene_name_cannot_escape_root(tmp_path):
    root = tmp_path / "scenes"
    (root / "公寓-客厅").mkdir(parents=True)
    (root / "公寓-客厅" / "白天.jpg").write_bytes(b"x")
    private = tmp_path / "private"
    private.mkdir()
    (private / "secret.jpg").write_bytes(b"x")
    assert pick_refs(root, "../private", DAY, 3) == []
    assert pick_refs(root, str(private), DAY, 3) == []


def make_dirs(root, folders):
    for folder in folders:
        (root / folder).mkdir(parents=True)
        (root / folder / "1.jpg").write_bytes(b"x")
    return root


def test_match_objects_in_order_of_appearance(tmp_path):
    root = make_dirs(tmp_path, ["芝士", "蛋挞", "兔球球"])
    assert match_objects(root, "蛋挞趴在芝士身上") == ["蛋挞", "芝士"]
    assert match_objects(root, "窗外下雨了") == []
    assert match_objects(tmp_path / "nope", "芝士") == []


def test_first_image(tmp_path):
    root = make_dirs(tmp_path, ["芝士"])
    assert first_image(root, "芝士").name == "1.jpg"
    assert first_image(root, "不存在") is None


WORK, SLEEP = (9, 18), (23, 7)
OUTFITS = ["制服-猎人制服", "便服-灰色卫衣", "便服-白衬衫", "睡衣-格子睡衣"]


def test_pick_outfit_by_schedule(tmp_path):
    root = make_dirs(tmp_path, OUTFITS)
    friday = datetime(2026, 10, 30)
    assert pick_outfit(root, friday.replace(hour=10), WORK, SLEEP) == "制服-猎人制服"
    assert pick_outfit(root, friday.replace(hour=20), WORK, SLEEP).startswith("便服-")
    assert pick_outfit(root, friday.replace(hour=23), WORK, SLEEP) == "睡衣-格子睡衣"
    assert pick_outfit(root, friday.replace(hour=3), WORK, SLEEP) == "睡衣-格子睡衣"
    saturday = datetime(2026, 10, 31, 10)
    assert pick_outfit(root, saturday, WORK, SLEEP).startswith("便服-")


def test_pick_outfit_fixed_within_day_and_rotates(tmp_path):
    root = make_dirs(tmp_path, OUTFITS)
    day = datetime(2026, 10, 31)
    picks = {pick_outfit(root, day.replace(hour=h), WORK, SLEEP) for h in (8, 12, 20)}
    assert len(picks) == 1
    next_day = pick_outfit(root, datetime(2026, 11, 1, 12), WORK, SLEEP)
    assert next_day != picks.pop()


def test_pick_outfit_missing_category_or_dir(tmp_path):
    root = make_dirs(tmp_path, ["便服-灰色卫衣"])
    assert pick_outfit(root, datetime(2026, 10, 30, 10), WORK, SLEEP) == "便服-灰色卫衣"
    assert pick_outfit(tmp_path / "nope", datetime(2026, 10, 30, 10), WORK, SLEEP) == ""


def test_outfit_day_starts_at_wake_up(tmp_path):
    root = make_dirs(tmp_path, ["睡衣-格子睡衣", "睡衣-白色睡衣", "便服-卫衣", "便服-衬衫"])
    night = pick_outfit(root, datetime(2026, 10, 30, 23, 30), WORK, SLEEP)
    after_midnight = pick_outfit(root, datetime(2026, 10, 31, 3), WORK, SLEEP)
    assert night == after_midnight and night.startswith("睡衣-")
    morning = pick_outfit(root, datetime(2026, 10, 31, 8), WORK, SLEEP)
    evening = pick_outfit(root, datetime(2026, 10, 31, 22), WORK, SLEEP)
    assert morning == evening


def test_outfit_category_and_next_change():
    friday = datetime(2026, 10, 30)
    assert outfit_category(friday.replace(hour=10), WORK, SLEEP) == "制服"
    assert next_category_change(friday.replace(hour=10, minute=30), WORK, SLEEP) == friday.replace(hour=18)
    assert next_category_change(friday.replace(hour=20), WORK, SLEEP) == friday.replace(hour=23)
    saturday = datetime(2026, 10, 31, 10)
    assert next_category_change(saturday, WORK, SLEEP) == saturday.replace(hour=23)
    assert next_category_change(friday.replace(hour=23, minute=5), WORK, SLEEP) == datetime(2026, 10, 31, 7)


OCCASION = ["便服-卫衣", "便服-衬衫", "制服-作战服", "睡衣-条纹", "正装-王储", "泳装-短裤"]


def test_wardrobe_adds_occasion_outfits(tmp_path):
    root = make_dirs(tmp_path, OCCASION)
    evening = datetime(2026, 10, 30, 20)
    assert wardrobe(root, evening, WORK, SLEEP) == [
        "便服-卫衣",
        "便服-衬衫",
        "正装-王储",
        "泳装-短裤",
    ]


def test_occasion_outfits_never_scheduled(tmp_path):
    root = make_dirs(tmp_path, ["便服-卫衣", "正装-王储", "泳装-短裤"])
    for hour in range(24):
        for day in (30, 31):
            picked = pick_outfit(root, datetime(2026, 10, day, hour), WORK, SLEEP)
            assert picked == "便服-卫衣"


def test_only_occasion_outfits_still_picks_something(tmp_path):
    root = make_dirs(tmp_path, ["正装-王储"])
    assert pick_outfit(root, datetime(2026, 10, 30, 20), WORK, SLEEP) == "正装-王储"


def test_scene_notes(tmp_path):
    root = make_dirs(tmp_path, ["公寓-厨房", "公寓-客厅"])
    (root / "公寓-厨房" / "说明.txt").write_text("  开放式厨房，没有窗户。\n", encoding="utf-8")
    assert scene_notes(root, "公寓-厨房") == "开放式厨房，没有窗户。"
    assert scene_notes(root, "公寓-客厅") == ""
    assert scene_notes(root, "不存在") == ""
    assert scene_notes(root, "../公寓-厨房") == ""
    (root / "公寓-客厅" / "说明.txt").write_text("长" * 500, encoding="utf-8")
    assert len(scene_notes(root, "公寓-客厅")) == 300
