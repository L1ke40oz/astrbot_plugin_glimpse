import json
from datetime import date

from data.plugins.astrbot_plugin_glimpse.album import Album


def test_save_and_count(tmp_path):
    album = Album(tmp_path / "album")
    path = album.save(
        b"\x89PNG fake",
        {
            "kind": "photo",
            "scene": "公寓-露台",
            "description": "猫",
            "prompt": "p",
            "refs": ["白天.jpg"],
            "session": "s",
        },
    )
    assert path.read_bytes() == b"\x89PNG fake" and path.suffix == ".png"
    lines = (tmp_path / "album" / "album.jsonl").read_text(encoding="utf-8").splitlines()
    line = json.loads(lines[0])
    assert line["description"] == "猫" and line["file"] == path.name and "created_at" in line
    assert album.count_on(date.today()) == 1
    assert album.count_on(date(2000, 1, 1)) == 0


def test_count_tolerates_garbage(tmp_path):
    album = Album(tmp_path)
    (tmp_path / "album.jsonl").write_text("not json\n", encoding="utf-8")
    assert album.count_on(date.today()) == 0
