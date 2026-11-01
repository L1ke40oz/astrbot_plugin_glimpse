import asyncio
import io
import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from astrbot.api.provider import ProviderRequest
from astrbot.core.message.message_event_result import (
    MessageEventResult,
    ResultContentType,
)
from data.plugins.astrbot_plugin_glimpse import main

SCHEMA = json.loads(
    (Path(main.__file__).parent / "_conf_schema.json").read_text(encoding="utf-8")
)
# Flat test overrides are routed to their config group using the schema.
GROUP_OF = {
    key: group
    for group, v in SCHEMA.items()
    if v["type"] == "object"
    for key in v["items"]
}
BASE_CONFIG = {
    "base_url": "https://relay.test/v1",
    "api_key": "k",
    "model": "gpt-image-2.5",
    "max_reference_images": 3,
}


def png(w, h):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, "PNG")
    return buf.getvalue()


def dims(data):
    return Image.open(io.BytesIO(data)).size


class FakeEvent:
    unified_msg_origin = "aiocqhttp:FriendMessage:1"

    def __init__(self, result):
        self._result = result

    def get_result(self):
        return self._result


@pytest.fixture
def make_event():
    def make(text, llm=True):
        result = MessageEventResult().message(text)
        result.set_result_content_type(
            ResultContentType.LLM_RESULT if llm else ResultContentType.GENERAL_RESULT
        )
        return FakeEvent(result)

    return make


@pytest.fixture
def calls(monkeypatch):
    seen = []

    async def fake_generate(session, base_url, api_key, model, prompt, size, refs):
        seen.append(
            {"prompt": prompt, "size": size, "refs": refs, "key": api_key, "model": model}
        )
        if api_key == "slow":
            await asyncio.sleep(10)
        if "坏" in prompt or api_key == "bad":
            raise RuntimeError("relay down")
        if "慢" in prompt:
            await asyncio.sleep(10)
        return png(1299, 1211)

    monkeypatch.setattr(main, "generate_image", fake_generate)
    return seen


@pytest.fixture
def make_plugin(tmp_path, monkeypatch, calls):
    monkeypatch.setattr(main.StarTools, "get_data_dir", lambda *a, **k: tmp_path)

    def make(**overrides):
        config = {g: {} for g, v in SCHEMA.items() if v["type"] == "object"}
        for key, value in {**BASE_CONFIG, **overrides}.items():
            config[GROUP_OF[key]][key] = value
        return main.Glimpse(MagicMock(), config)

    return make


@pytest.fixture
def plugin(make_plugin):
    return make_plugin()


def kinds(event):
    return [type(c).__name__ for c in event.get_result().chain]


@pytest.mark.asyncio
async def test_replaces_marker_in_place(plugin, make_event):
    ev = make_event("刚回来$[📷拍照·公寓-露台：橘猫]$你看")
    await plugin.render_markers(ev)
    chain = ev.get_result().chain
    assert kinds(ev) == ["Plain", "Image", "Plain"]
    assert chain[0].text == "刚回来$" and chain[2].text == "$你看"
    assert plugin.album.count_on(date.today()) == 1


@pytest.mark.asyncio
async def test_generation_error_falls_back(plugin, make_event):
    ev = make_event("[📷拍照：坏][✏️涂鸦：好]")
    await plugin.render_markers(ev)
    chain = ev.get_result().chain
    assert kinds(ev) == ["Plain", "Image"]
    assert chain[0].text == "[📷分享图片：坏]"


@pytest.mark.asyncio
async def test_timeout_falls_back(make_plugin, make_event):
    plugin = make_plugin(timeout_seconds=0.1)
    ev = make_event("a[📷拍照：慢]b")
    await plugin.render_markers(ev)
    assert [c.text for c in ev.get_result().chain] == ["a[📷分享图片：慢]b"]


@pytest.mark.asyncio
async def test_cap_and_quota_fallback(make_plugin, make_event):
    plugin = make_plugin(enable_daily_limit=True, daily_limit=2)
    plugin.album.save(b"old", {"kind": "photo"})
    ev = make_event("[📷拍照：1][📷拍照：2][📷拍照：3][📷拍照：4]")
    await plugin.render_markers(ev)
    assert kinds(ev) == ["Image", "Plain"]
    assert ev.get_result().chain[1].text == "[📷分享图片：2][📷分享图片：3][📷分享图片：4]"


@pytest.mark.asyncio
async def test_reply_cap_without_limit(plugin, make_event, calls):
    ev = make_event("[📷拍照：1][📷拍照：2][📷拍照：3][📷拍照：4]")
    await plugin.render_markers(ev)
    assert kinds(ev) == ["Image", "Image", "Image", "Plain"]
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_unconfigured_falls_back(make_plugin, make_event, calls):
    plugin = make_plugin(api_key="")
    ev = make_event("[✏️涂鸦：兔子]")
    await plugin.render_markers(ev)
    assert ev.get_result().chain[0].text == "[✏️涂鸦：兔子]"
    assert calls == []


@pytest.mark.asyncio
async def test_non_llm_result_untouched(plugin, make_event, calls):
    ev = make_event("[📷拍照：猫]", llm=False)
    await plugin.render_markers(ev)
    assert ev.get_result().chain[0].text == "[📷拍照：猫]"
    assert calls == []


@pytest.fixture
def plugin_with_scenes(make_plugin, tmp_path):
    scene = tmp_path / "scenes" / "公寓-露台"
    scene.mkdir(parents=True)
    (scene / "白天.jpg").write_bytes(png(1260, 1175))
    (scene / "夜晚.jpg").write_bytes(png(1260, 1175))
    return make_plugin()


@pytest.mark.asyncio
async def test_scene_refs_passed(plugin_with_scenes, make_event, calls):
    await plugin_with_scenes.render_markers(make_event("[📷拍照·公寓-露台：猫]"))
    assert len(calls[-1]["refs"]) == 1 and calls[-1]["size"] == "1024x1536"
    name, data = calls[-1]["refs"][0]
    assert name.endswith(".jpg") and dims(data) == (881, 1175)
    await plugin_with_scenes.render_markers(make_event("[✏️涂鸦·公寓-露台：猫]"))
    assert calls[-1]["refs"] == [] and calls[-1]["size"] == "1024x1024"


@pytest.mark.asyncio
async def test_inject_guide(plugin_with_scenes):
    req = ProviderRequest(system_prompt="人设")
    await plugin_with_scenes.inject_guide(MagicMock(), req)
    assert req.system_prompt.startswith("人设\n\n")
    assert "公寓-露台" in req.system_prompt


@pytest.mark.asyncio
async def test_streaming_finish_skipped(plugin, make_event, calls):
    ev = make_event("[📷拍照：猫]")
    ev.get_result().set_result_content_type(ResultContentType.STREAMING_FINISH)
    await plugin.render_markers(ev)
    assert calls == [] and plugin.album.count_on(date.today()) == 0


@pytest.mark.asyncio
async def test_output_cropped_per_kind(plugin, make_event, calls):
    for text, size, ratio in (
        ("[📷拍照：猫]", "1024x1536", 3 / 4),
        ("[🎞️胶片：海]", "1536x1024", 3 / 2),
        ("[✏️涂鸦：兔]", "1024x1024", 1),
    ):
        ev = make_event(text)
        await plugin.render_markers(ev)
        image = ev.get_result().chain[0]
        w, h = Image.open(image.path).size
        assert calls[-1]["size"] == size and abs(w / h - ratio) < 0.01


BACKUP = {"base_url": "https://backup.test/v1", "api_key": "k2", "model": "m2"}


@pytest.mark.asyncio
async def test_photo_style_option(make_plugin, make_event, calls):
    await make_plugin(photo_style="氛围大片").render_markers(make_event("[📷拍照：猫]"))
    assert "quick snapshot of a small moment" in calls[-1]["prompt"]
    await make_plugin().render_markers(make_event("[📷拍照：猫]"))
    assert "unedited" in calls[-1]["prompt"]


@pytest.mark.asyncio
async def test_falls_back_to_backup_provider(make_plugin, make_event, calls):
    plugin = make_plugin(api_key="bad", backup_providers=[BACKUP])
    ev = make_event("[📷拍照：猫]")
    await plugin.render_markers(ev)
    assert kinds(ev) == ["Image"]
    assert [(c["key"], c["model"]) for c in calls] == [("bad", "gpt-image-2.5"), ("k2", "m2")]
    line = (plugin.album.meta_path).read_text(encoding="utf-8")
    assert '"model": "m2"' in line


@pytest.mark.asyncio
async def test_slow_primary_times_out_then_backup(make_plugin, make_event, calls):
    plugin = make_plugin(api_key="slow", timeout_seconds=0.1, backup_providers=[BACKUP])
    ev = make_event("[📷拍照：猫]")
    await plugin.render_markers(ev)
    assert kinds(ev) == ["Image"] and calls[-1]["key"] == "k2"


@pytest.mark.asyncio
async def test_all_providers_fail_falls_back_to_text(make_plugin, make_event, calls):
    plugin = make_plugin(
        api_key="bad", backup_providers=[{**BACKUP, "api_key": "bad"}]
    )
    ev = make_event("[📷拍照：猫]")
    await plugin.render_markers(ev)
    assert ev.get_result().chain[0].text == "[📷分享图片：猫]" and len(calls) == 2


@pytest.mark.asyncio
async def test_incomplete_backup_skipped_and_backup_only_works(
    make_plugin, make_event, calls
):
    plugin = make_plugin(
        api_key="", backup_providers=[{**BACKUP, "model": ""}, BACKUP]
    )
    ev = make_event("[📷拍照：猫]")
    await plugin.render_markers(ev)
    assert kinds(ev) == ["Image"] and [c["key"] for c in calls] == ["k2"]


def test_schema_guide_default_matches_builtin():
    from data.plugins.astrbot_plugin_glimpse.prompts import DEFAULT_GUIDE

    guide = SCHEMA["guide_config"]["items"]
    assert guide["guide_prompt"]["default"] == DEFAULT_GUIDE
    assert guide["enable_guide"]["default"] is True


@pytest.mark.asyncio
async def test_guide_can_be_disabled(make_plugin):
    req = ProviderRequest(system_prompt="人设")
    await make_plugin(enable_guide=False).inject_guide(MagicMock(), req)
    assert req.system_prompt == "人设"


@pytest.mark.asyncio
async def test_custom_guide_used(make_plugin):
    req = ProviderRequest(system_prompt="人设")
    await make_plugin(guide_prompt="自定义 {scenes}").inject_guide(MagicMock(), req)
    assert req.system_prompt == "人设\n\n自定义 （暂无）"


def write_lib(root, folders, size=(1260, 1175)):
    for folder in folders:
        (root / folder).mkdir(parents=True, exist_ok=True)
        (root / folder / "1.jpg").write_bytes(png(*size))


@pytest.mark.asyncio
async def test_object_reference_added(make_plugin, make_event, calls, tmp_path):
    write_lib(tmp_path / "objects", ["芝士", "蛋挞"])
    await make_plugin().render_markers(make_event("[📷拍照：芝士在窗台上打盹]"))
    assert len(calls[-1]["refs"]) == 1
    assert "Reference image 1: 芝士" in calls[-1]["prompt"]


@pytest.mark.asyncio
async def test_reference_priority_and_cap(make_plugin, make_event, calls, tmp_path):
    write_lib(tmp_path / "objects", ["芝士", "蛋挞", "兔球球"])
    write_lib(tmp_path / "scenes", ["公寓-客厅"])
    (tmp_path / "scenes" / "公寓-客厅" / "2.jpg").write_bytes(png(10, 10))
    plugin = make_plugin(max_reference_images=4)
    await plugin.render_markers(make_event("[📷拍照·公寓-客厅：芝士蛋挞兔球球挤在沙发上]"))
    prompt = calls[-1]["prompt"]
    assert len(calls[-1]["refs"]) == 4
    assert "Reference image 3: 兔球球" in prompt and "Reference image 4: the room" in prompt


@pytest.mark.asyncio
async def test_hands_only_when_described_and_enabled(
    make_plugin, make_event, calls, tmp_path
):
    write_lib(tmp_path / "outfits", ["便服-灰色卫衣"])
    (tmp_path / "hands").mkdir()
    (tmp_path / "hands" / "hand.jpg").write_bytes(png(800, 600))
    plugin = make_plugin(allow_hands=True)
    await plugin.render_markers(make_event("[📷拍照：我手里捏着糖炒栗子]"))
    prompt = calls[-1]["prompt"]
    assert "his own hand" in prompt and "no hands," not in prompt
    assert "便服-灰色卫衣" in prompt
    assert [n for n, _ in calls[-1]["refs"]] == ["1.jpg", "hand.jpg"]
    await plugin.render_markers(make_event("[📷拍照：手机屏幕亮了]"))
    assert "holding or touching" in calls[-1]["prompt"] and calls[-1]["refs"] == []
    await make_plugin().render_markers(make_event("[📷拍照：我手里捏着糖炒栗子]"))
    assert "no hands" in calls[-1]["prompt"]


@pytest.mark.asyncio
async def test_guide_mentions_objects_and_outfit(make_plugin, tmp_path):
    write_lib(tmp_path / "objects", ["芝士"])
    write_lib(tmp_path / "outfits", ["便服-灰色卫衣"])
    req = ProviderRequest(system_prompt="人设")
    await make_plugin().inject_guide(MagicMock(), req)
    assert "芝士" in req.system_prompt and "便服-灰色卫衣" in req.system_prompt


@pytest.mark.asyncio
async def test_bad_reference_skipped(make_plugin, make_event, calls, tmp_path):
    write_lib(tmp_path / "objects", ["芝士", "蛋挞"])
    (tmp_path / "objects" / "芝士" / "1.jpg").write_bytes(b"not an image")
    ev = make_event("[📷拍照：芝士和蛋挞]")
    await make_plugin().render_markers(ev)
    assert kinds(ev) == ["Image"]
    prompt = calls[-1]["prompt"]
    assert "Reference image 1: 蛋挞" in prompt and "芝士," not in prompt
    [(name, data)] = calls[-1]["refs"]
    assert name == "1.jpg" and Image.open(io.BytesIO(data)).format == "JPEG"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text, hands",
    [
        ("[📷拍照：我手中的咖啡]", True),
        ("[📷拍照：双手捧着热可可]", True),
        ("[📷拍照：卷起的袖子上沾了面粉]", True),
        ("[📷拍照：手里拿着一张菜单]", True),
        ("[📷拍照：端着一杯咖啡]", True),
        ("[📷拍照：一盒手指饼干]", False),
        ("[📷拍照：窗台上的袖珍盆栽]", False),
        ("[📷拍照：电视里选手上场了]", False),
    ],
)
async def test_hand_keywords(make_plugin, make_event, calls, tmp_path, text, hands):
    write_lib(tmp_path / "outfits", ["便服-灰色卫衣"])
    await make_plugin(allow_hands=True).render_markers(make_event(text))
    assert bool(calls[-1]["refs"]) is hands


@pytest.mark.asyncio
async def test_outfit_change_marker_stripped_and_followed(make_plugin, make_event, tmp_path):
    write_lib(tmp_path / "outfits", ["便服-卫衣", "便服-衬衫", "睡衣-格子"])
    plugin = make_plugin()
    ev = make_event("等我一下[👕换装：便服-衬衫]$换好了")
    await plugin.render_markers(ev)
    assert [c.text for c in ev.get_result().chain] == ["等我一下$换好了"]
    override = json.loads((tmp_path / "outfit_override.json").read_text(encoding="utf-8"))
    assert override["outfit"] == "便服-衬衫"
    req = ProviderRequest(system_prompt="")
    await plugin.inject_guide(MagicMock(), req)
    if "穿的是：便服-衬衫" not in req.system_prompt:
        assert "睡衣" in req.system_prompt  # tested during the sleep window
    assert "可换的有：" in req.system_prompt


@pytest.mark.asyncio
async def test_invalid_outfit_change_ignored(make_plugin, make_event, tmp_path):
    write_lib(tmp_path / "outfits", ["便服-卫衣"])
    ev = make_event("[👕换装：西装]好")
    await make_plugin().render_markers(ev)
    assert ev.get_result().chain[0].text == "好"
    assert not (tmp_path / "outfit_override.json").exists()


def test_expired_outfit_override_ignored(make_plugin, tmp_path):
    write_lib(tmp_path / "outfits", ["便服-卫衣", "便服-衬衫"])
    (tmp_path / "outfit_override.json").write_text(
        json.dumps({"outfit": "便服-衬衫", "until": "2000-01-01T00:00:00"}), encoding="utf-8"
    )
    plugin = make_plugin()
    from datetime import datetime as dt

    now = dt(2026, 10, 31, 12)
    expected = main.pick_outfit(plugin.dirs["outfits"], now, (9, 18), (23, 7))
    assert plugin._current_outfit(now) == expected


@pytest.mark.asyncio
async def test_keyword_guard(make_plugin, make_event, calls):
    plugin = make_plugin(enable_keyword_guard=True)
    ev = make_event("[📷拍照：对着镜子拍了一张]")
    await plugin.render_markers(ev)
    assert ev.get_result().chain[0].text == "[📷分享图片：对着镜子拍了一张]" and calls == []
    await plugin.render_markers(make_event("[✏️涂鸦：自拍的我]"))
    assert len(calls) == 1
    await make_plugin().render_markers(make_event("[📷拍照：对着镜子拍了一张]"))
    assert len(calls) == 2


class FakeVisionProvider:
    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    async def text_chat(self, prompt=None, image_urls=None, **kwargs):
        self.calls.append((prompt, list(image_urls or [])))
        assert Path(image_urls[0]).exists()
        if isinstance(self.answer, Exception):
            raise self.answer
        return MagicMock(completion_text=self.answer)


@pytest.mark.asyncio
async def test_face_check_blocks_face(make_plugin, make_event):
    plugin = make_plugin(enable_face_check=True, face_check_provider="vision")
    vision = FakeVisionProvider("**YES**")
    plugin.context.get_provider_by_id = MagicMock(return_value=vision)
    ev = make_event("[📷拍照：小猫爬到我肩膀上]")
    await plugin.render_markers(ev)
    assert ev.get_result().chain[0].text == "[📷分享图片：小猫爬到我肩膀上]"
    plugin.context.get_provider_by_id.assert_called_with("vision")
    assert vision.calls and plugin.album.count_on(date.today()) == 0
    assert not list(plugin.data_dir.glob("face-check-*"))


@pytest.mark.asyncio
async def test_face_check_passes_and_errors_allow(make_plugin, make_event):
    plugin = make_plugin(enable_face_check=True)
    plugin.context.get_using_provider = MagicMock(return_value=FakeVisionProvider("No."))
    ev = make_event("[📷拍照：窗外]")
    await plugin.render_markers(ev)
    assert kinds(ev) == ["Image"]
    plugin.context.get_using_provider = MagicMock(
        return_value=FakeVisionProvider(RuntimeError("vision down"))
    )
    ev = make_event("[📷拍照：窗外]")
    await plugin.render_markers(ev)
    assert kinds(ev) == ["Image"]
    plugin.context.get_using_provider = MagicMock(return_value=None)
    ev = make_event("[📷拍照：窗外]")
    await plugin.render_markers(ev)
    assert kinds(ev) == ["Image"]


@pytest.mark.asyncio
async def test_face_check_off_by_default(plugin, make_event):
    plugin.context.get_using_provider = MagicMock()
    await plugin.render_markers(make_event("[📷拍照：窗外]"))
    plugin.context.get_using_provider.assert_not_called()


@pytest.mark.asyncio
async def test_keyword_guard_accepts_chinese_separators(make_plugin, make_event, calls):
    plugin = make_plugin(enable_keyword_guard=True, guard_keywords="合照、镜子 出镜")
    for text in ("[📷拍照：镜子前]", "[📷拍照：出镜一下]", "[📷拍照：合照]"):
        await plugin.render_markers(make_event(text))
    assert calls == []


@pytest.mark.asyncio
async def test_outfit_only_reply_leaves_no_empty_message(make_plugin, make_event, tmp_path):
    write_lib(tmp_path / "outfits", ["便服-卫衣"])
    result = MessageEventResult().message("[👕换装：便服-卫衣]")
    result.chain.append(main.Plain("换好啦"))
    result.set_result_content_type(ResultContentType.LLM_RESULT)
    ev = FakeEvent(result)
    await make_plugin().render_markers(ev)
    assert [c.text for c in ev.get_result().chain] == ["换好啦"]


@pytest.mark.asyncio
async def test_override_write_failure_still_renders(make_plugin, make_event, tmp_path, monkeypatch):
    write_lib(tmp_path / "outfits", ["便服-卫衣"])
    plugin = make_plugin()

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(type(plugin.override_path), "write_text", boom)
    ev = make_event("[👕换装：便服-卫衣][📷拍照：窗外]")
    await plugin.render_markers(ev)
    assert kinds(ev) == ["Image"]


def test_schema_prompt_defaults_match_builtin():
    from data.plugins.astrbot_plugin_glimpse.prompts import PROMPT_DEFAULTS

    items = SCHEMA["prompt_config"]["items"]
    assert {k: v["default"] for k, v in items.items()} == PROMPT_DEFAULTS


def test_default_library_dirs_created(make_plugin, tmp_path):
    custom = tmp_path / "my_scenes"
    make_plugin(scenes_dir=str(custom))
    for name in ("objects", "outfits", "hands"):
        assert (tmp_path / name).is_dir()
    assert not (tmp_path / "scenes").exists() and not custom.exists()


def test_advanced_groups_hidden_behind_toggle():
    assert SCHEMA["show_advanced"]["type"] == "bool"
    assert SCHEMA["show_advanced"]["default"] is False
    for group in ("prompt_config", "guard_config"):
        assert SCHEMA[group]["condition"] == {"show_advanced": True}
    assert SCHEMA["guard_config"]["items"]["face_check_provider"]["_special"] == "select_provider"


@pytest.mark.asyncio
async def test_room_notes_sent_for_scene(make_plugin, make_event, calls, tmp_path):
    write_lib(tmp_path / "scenes", ["公寓-厨房"])
    (tmp_path / "scenes" / "公寓-厨房" / "说明.txt").write_text("没有窗户", encoding="utf-8")
    plugin = make_plugin()
    await plugin.render_markers(make_event("[📷拍照·公寓-厨房：锅里的面]"))
    assert "没有窗户" in calls[-1]["prompt"]
    await plugin.render_markers(make_event("[✏️涂鸦·公寓-厨房：做饭]"))
    assert "没有窗户" not in calls[-1]["prompt"]


@pytest.mark.asyncio
async def test_logs_unparsed_marker(plugin, make_event, calls, caplog):
    import logging

    with caplog.at_level(logging.INFO):
        await plugin.render_markers(make_event("[📷拍照/公寓：锅]"))
    assert calls == []
    assert "could not be parsed" in caplog.text


@pytest.mark.asyncio
async def test_logs_missing_provider(make_plugin, make_event, caplog):
    import logging

    with caplog.at_level(logging.INFO):
        await make_plugin(api_key="").render_markers(make_event("[📷拍照：猫]"))
    assert "no complete image provider" in caplog.text


@pytest.mark.asyncio
async def test_logs_success(plugin, make_event, caplog):
    import logging

    with caplog.at_level(logging.INFO):
        await plugin.render_markers(make_event("[📷拍照：猫]"))
    assert "found 1 marker" in caplog.text and "generated by gpt-image-2.5" in caplog.text
