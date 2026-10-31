# 沈星回的手机 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把沈星回回复里的 `[📷拍照：…]` / `[🎞️胶片：…]` / `[✏️涂鸦：…]` 标记，在发送前替换成 gpt-image 生成的真图；失败时退回文字。

**Architecture:** 纯逻辑放在不依赖 AstrBot 的小模块里，分别负责标记解析、场景挑图、提示词模板和相册存储；HTTP 调用放在 `image_client.py`；`main.py` 只做两件事：在 `on_llm_request` 里注入使用说明，在 `on_decorating_result` 里并发生成图片，并一次性替换消息链。

**Tech Stack:** Python 3.10+、AstrBot 4.x 插件 API、aiohttp、pytest + pytest-asyncio（AstrBot 的 uv 环境自带）。

**Spec:** `docs/superpowers/specs/2026-10-31-xavier-phone-design.md`

## Global Constraints

- 插件目录：`D:\Software\AstrBot-master\data\plugins\astrbot_plugin_xavier_phone`，git 分支 `master`，远程 `origin`。下文路径都相对这个目录。
- 测试命令都在 AstrBot 根目录执行：`uv run --no-sync python -m pytest data/plugins/astrbot_plugin_xavier_phone/tests -q`。测试用 `from data.plugins.astrbot_plugin_xavier_phone.<module> import ...` 导入；插件内部模块之间用相对导入。
- 异步测试使用 `@pytest.mark.asyncio`（AstrBot 未开启 auto 模式）。
- `markers.py`、`scenes.py`、`prompts.py`、`album.py` 不得 import astrbot。
- 用 `pathlib.Path`；注释和日志用英文；docstring 用 Google 风格；遵守 AGENTS.md 的 KISS 和“不加不必要的 helper”。
- 每个任务结束前，在插件目录运行 `uv run --no-sync ruff format . && uv run --no-sync ruff check .`，并且要通过。
- 提交信息使用 conventional commits，并以 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` 结尾。
- 配置默认值：`base_url=""`（由用户填写）、`model=gpt-image-2.5`、`timeout_seconds=90`、`photo_size=1024x1536`、`doodle_size=1024x1024`、`max_reference_images=3`、`enable_daily_limit=false`、`daily_limit=10`、`scenes_dir=""`（空表示数据目录下的 `scenes/`）。
- 每条回复最多生成 3 张图（`MAX_MARKERS_PER_REPLY = 3`）；“白天”定义为本机时间 6 ≤ hour < 18。
- 回退文字：拍照和胶片回退为 `[📷分享图片：{描述}]`，涂鸦回退为 `[✏️涂鸦：{描述}]`。
- 永远不要把提示词、错误信息或残缺的标记发给用户。

## Review Focus

1. **回复里的标记超过 3 个，或当天额度已用完**：前面的生成图片，其余退回文字，且顺序不乱。测试见 Task 6 的 `test_cap_and_quota_fallback`。
2. **中转站返回 200 但没有图、返回错误 JSON，或网络异常**：该标记退回文字，其他标记不受影响。测试见 Task 5 的 `test_no_image_raises` 和 Task 6 的 `test_generation_error_falls_back`。
3. **生成超时**：退回文字，整条回复照常发出。测试见 Task 6 的 `test_timeout_falls_back`。
4. **非 LLM 回复（指令、其他插件），以及旧的 `[📷分享图片：…]` 标记**：一律不动。测试见 Task 1 的 `test_ignores_share_marker` 和 Task 6 的 `test_non_llm_result_untouched`。
5. **场景目录不存在或为空、场景名写错**：退化为纯文生图，使用说明里显示“（暂无）”，不崩溃。测试见 Task 2 的 `test_missing_scene_dir` 和 Task 3 的 `test_guide_no_scenes`。

---

### Task 1: 插件骨架 + 标记解析

**Files:**
- Modify: `metadata.yaml`（替换模板内容）
- Delete: `main.py` 中 helloworld 的内容（Task 6 会重写，这里先清空成占位的 docstring，防止 AstrBot 加载模板）
- Create: `markers.py`
- Create: `tests/__init__.py`（空文件）、`tests/test_markers.py`

**Interfaces:**
- Produces:
  - `Marker`：frozen dataclass，字段为 `kind: str`（取值 `"photo"`、`"film"`、`"doodle"`）、`scene: str`（无场景时为 `""`；涂鸦总是 `""`）、`description: str`、`start: int`、`end: int`（在原文本中的切片位置）。
  - `parse_markers(text: str) -> list[Marker]`：按出现顺序返回。
  - `fallback_text(marker: Marker) -> str`

- [ ] **Step 1: 写 metadata.yaml**

```yaml
name: astrbot_plugin_xavier_phone
display_name: 沈星回的手机
desc: 把沈星回聊天中的拍照、胶片、涂鸦标记变成真图。
version: v0.1.0
author: L1ke40oz
repo: https://github.com/L1ke40oz/astrbot_plugin_xavier_phone
astrbot_version: ">=4.16,<5"
```

- [ ] **Step 2: 写失败测试 `tests/test_markers.py`**

```python
from data.plugins.astrbot_plugin_xavier_phone.markers import fallback_text, parse_markers

def test_photo_with_scene():
    text = "刚回家$[📷拍照·公寓-露台：吊椅上睡着一只橘猫，星星灯刚亮]$你看"
    [m] = parse_markers(text)
    assert (m.kind, m.scene, m.description) == ("photo", "公寓-露台", "吊椅上睡着一只橘猫，星星灯刚亮")
    assert text[m.start:m.end] == "[📷拍照·公寓-露台：吊椅上睡着一只橘猫，星星灯刚亮]"

def test_loose_variants():
    assert parse_markers("[拍照:海边的落日]")[0].kind == "photo"           # no emoji, ASCII colon
    assert parse_markers("[📷照片：猫]")[0].kind == "photo"                 # 照片 alias
    assert parse_markers("[🎞️胶片-邱诺亚的花店：门口的风铃]")[0].scene == "邱诺亚的花店"  # '-' separator
    assert parse_markers("[ ✏️ 涂鸦 ： 钓到一条鱼（并没有） ]")[0].description == "钓到一条鱼（并没有）"

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
```

- [ ] **Step 3: 运行测试，确认失败（ImportError）**

- [ ] **Step 4: 实现 `markers.py`**

使用这个正则（`re.compile`），kind 映射为 `{"拍照": "photo", "照片": "photo", "胶片": "film", "涂鸦": "doodle"}`：

```python
MARKER_RE = re.compile(
    r"\[\s*(?:📷|🎞️|🎞|✏️|✏)?\s*(拍照|照片|胶片|涂鸦)\s*"
    r"(?:[·・\-—]\s*([^:：\]]+?)\s*)?[:：]\s*([^\]]+?)\s*\]"
)
```

- [ ] **Step 5: 运行测试，确认全部通过，再跑 ruff**

- [ ] **Step 6: 提交**

```bash
git add metadata.yaml main.py markers.py tests/
git commit -m "feat: add plugin skeleton and marker parser"
```

---

### Task 2: 场景库挑图

**Files:**
- Create: `scenes.py`、`tests/test_scenes.py`

**Interfaces:**
- Produces:
  - `list_scenes(root: Path) -> list[str]`：返回含有图片的子文件夹名，按名称排序；目录不存在时返回 `[]`。
  - `pick_refs(root: Path, scene: str, now: datetime, max_refs: int) -> list[Path]`
- 图片后缀：`.jpg`、`.jpeg`、`.png`、`.webp`（不区分大小写）。

- [ ] **Step 1: 写失败测试**

用 `tmp_path` 搭建这样的目录：`公寓-客厅/{白天.jpg,夜晚.jpg,客厅全景.jpg}`、`公寓-卧室/夜晚.jpg`、`空文件夹/`、`公寓-厨房/{厨房.jpg,notes.txt}`。

```python
DAY, NIGHT = datetime(2026, 10, 31, 10), datetime(2026, 10, 31, 22)

def test_list_scenes(scene_root):
    assert list_scenes(scene_root) == ["公寓-卧室", "公寓-厨房", "公寓-客厅"]  # sorted; empty folder excluded

def test_missing_scene_dir(tmp_path):
    assert list_scenes(tmp_path / "nope") == []
    assert pick_refs(tmp_path / "nope", "公寓-客厅", DAY, 3) == []

def test_time_tagged_first_then_untagged(scene_root):
    assert [p.name for p in pick_refs(scene_root, "公寓-客厅", DAY, 3)] == ["白天.jpg", "客厅全景.jpg"]
    assert [p.name for p in pick_refs(scene_root, "公寓-客厅", NIGHT, 3)] == ["夜晚.jpg", "客厅全景.jpg"]

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
```

- [ ] **Step 2: 运行测试，确认失败**
- [ ] **Step 3: 实现 `scenes.py`**

挑图规则：图片按文件名排序。文件名 stem 含“白天”或“夜晚”的算带时段的图；先放与当前时段匹配的带时段图，再放不带时段的图。如果结果为空，就用该文件夹的全部图片。最后截取前 `max_refs` 张。

- [ ] **Step 4: 运行测试，确认通过；跑 ruff**
- [ ] **Step 5: 提交** `feat: add scene reference picker`

---

### Task 3: 提示词模板与使用说明

**Files:**
- Create: `prompts.py`、`tests/test_prompts.py`

**Interfaces:**
- Consumes: Task 1 的 `Marker`
- Produces:
  - `build_prompt(marker: Marker, has_refs: bool, now: datetime) -> str`
  - `DEFAULT_GUIDE: str`：中文使用说明，必须包含占位符 `{scenes}`。
  - `build_guide(template: str, scenes: list[str]) -> str`：用 `str.replace("{scenes}", ...)` 替换，场景之间用 `、` 连接；没有场景时填“（暂无）”。不要用 `str.format`，因为用户自定义的说明里可能带有花括号。

- [ ] **Step 1: 写失败测试**

```python
def test_photo_prompt_rules():
    p = build_prompt(parse_markers("[📷拍照：阳台上的小鸟]")[0], False, DAY)
    assert "阳台上的小鸟" in p
    for phrase in ("smartphone", "first-person", "no human faces", "no hands", "daytime"):
        assert phrase in p
    assert "same room" not in p

def test_night_and_refs():
    p = build_prompt(parse_markers("[📷拍照·公寓-露台：吊椅]")[0], True, NIGHT)
    assert "night" in p and "same room" in p and "different angle" in p

def test_film_prompt():
    p = build_prompt(parse_markers("[🎞️胶片：海]")[0], False, DAY)
    assert "film" in p and "no hands" in p

def test_doodle_prompt():
    p = build_prompt(parse_markers("[✏️涂鸦：钓鱼]")[0], False, DAY)
    for phrase in ("doodle", "thick black", "white background", "silver", "fang", "no text"):
        assert phrase in p
    assert "smartphone" not in p

def test_guide():
    g = build_guide(DEFAULT_GUIDE, ["公寓-客厅", "邱诺亚的花店"])
    assert "公寓-客厅、邱诺亚的花店" in g and "[📷拍照" in g and "[✏️涂鸦" in g and "[📷分享图片" in g

def test_guide_no_scenes():
    assert "（暂无）" in build_guide(DEFAULT_GUIDE, [])
    assert build_guide("{x} {scenes}", ["a"]) == "{x} a"
```

- [ ] **Step 2: 运行测试，确认失败**
- [ ] **Step 3: 实现 `prompts.py`**

英文模板用模块常量 `PHOTO_TEMPLATE`、`FILM_TEMPLATE`、`DOODLE_TEMPLATE`，措辞要满足设计文档 7.4 的要点，并包含上面测试里断言的短语。描述原样以中文嵌入，例如 `Scene: {description}`。光线句根据 `now` 选 `daytime` 或 `night`。`has_refs` 为真时追加：`The reference images show the same room; shoot a different angle or a close-up corner, do not copy the reference composition.` 涂鸦不加光线句和参考图句。

`DEFAULT_GUIDE` 内容覆盖设计文档 7.6 的全部要点：三种标记的写法和例子、`{scenes}` 场景列表、“涉及你自己的照片继续用 `[📷分享图片：…]` 文字版”、“描述写一两句具体画面（主体、环境、光线）”、“按心情偶尔使用，不必每次都发”。

- [ ] **Step 4: 运行测试，确认通过；跑 ruff**
- [ ] **Step 5: 提交** `feat: add prompt templates and usage guide`

---

### Task 4: 相册存储

**Files:**
- Create: `album.py`、`tests/test_album.py`

**Interfaces:**
- Produces: `class Album`
  - `__init__(self, root: Path)`：根目录不存在时创建；元数据文件为 `root / "album.jsonl"`。
  - `save(self, image: bytes, meta: dict) -> Path`：图片文件名为 `{YYYYmmdd-HHMMSS}-{uuid4().hex[:8]}.png`，写入 `root`；在 jsonl 末尾追加一行 `{**meta, "file": 文件名, "created_at": ISO 时间（秒精度，本地时间）}`，`ensure_ascii=False`；返回图片路径。
  - `count_on(self, day: date) -> int`：统计 `created_at` 日期为 `day` 的行数；文件不存在时返回 0；跳过坏行。

- [ ] **Step 1: 写失败测试**

```python
def test_save_and_count(tmp_path):
    album = Album(tmp_path / "album")
    path = album.save(b"\x89PNG fake", {"kind": "photo", "scene": "公寓-露台", "description": "猫", "prompt": "p", "refs": ["白天.jpg"], "session": "s"})
    assert path.read_bytes() == b"\x89PNG fake" and path.suffix == ".png"
    line = json.loads((tmp_path / "album" / "album.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert line["description"] == "猫" and line["file"] == path.name and "created_at" in line
    assert album.count_on(date.today()) == 1
    assert album.count_on(date(2000, 1, 1)) == 0

def test_count_tolerates_garbage(tmp_path):
    album = Album(tmp_path)
    (tmp_path / "album.jsonl").write_text("not json\n", encoding="utf-8")
    assert album.count_on(date.today()) == 0
```

- [ ] **Step 2: 运行测试，确认失败**
- [ ] **Step 3: 实现 `album.py`**
- [ ] **Step 4: 运行测试，确认通过；跑 ruff**
- [ ] **Step 5: 提交** `feat: add album storage`

---

### Task 5: gpt-image 客户端

**Files:**
- Create: `image_client.py`、`tests/test_image_client.py`

**Interfaces:**
- Produces: `async def generate_image(session: aiohttp.ClientSession, base_url: str, api_key: str, model: str, prompt: str, size: str, refs: list[Path]) -> bytes`
  - 没有 `refs` 时：`POST {base_url.rstrip('/')}/images/generations`，JSON 为 `{"model", "prompt", "size", "n": 1}`。
  - 有 `refs` 时：`POST .../images/edits`，multipart 字段为 `model`、`prompt`、`size`、`n=1`。只有一张图时用字段名 `image`，多张时每张用 `image[]`。content_type 按后缀推断。
  - Header：`Authorization: Bearer {api_key}`。
  - 响应取 `data[0]`：有 `b64_json` 就 base64 解码；有 `url` 就用同一个 session GET 下载。
  - HTTP 状态 ≥ 400，或没有可用的图，就抛 `RuntimeError`（消息里只带状态码和截断的响应前 200 字，不带 key）。
  - 超时由调用方的 `asyncio.wait_for` 负责，这里不设。

- [ ] **Step 1: 写失败测试**

用 `aiohttp.web` 在 `aiohttp.test_utils.TestServer` 上起一个假的中转站，记录收到的请求。

```python
@pytest.mark.asyncio
async def test_generations_b64(fake_relay):          # relay returns {"data":[{"b64_json": base64(b"IMG")}]}
    out = await generate_image(fake_relay.session, fake_relay.base_url, "k", "gpt-image-2.5", "p", "1024x1536", [])
    assert out == b"IMG"
    req = fake_relay.requests[-1]
    assert req.path == "/v1/images/generations" and req.json["model"] == "gpt-image-2.5" and req.headers["Authorization"] == "Bearer k"

@pytest.mark.asyncio
async def test_edits_multi_image_and_url(fake_relay, tmp_path):   # relay returns {"data":[{"url": ".../file.png"}]} serving b"URLIMG"
    a, b = tmp_path / "白天.jpg", tmp_path / "全景.jpg"; a.write_bytes(b"A"); b.write_bytes(b"B")
    out = await generate_image(..., refs=[a, b])
    assert out == b"URLIMG"
    assert fake_relay.requests[-2].path == "/v1/images/edits" and fake_relay.requests[-2].image_field_names == ["image[]", "image[]"]

@pytest.mark.asyncio
async def test_edits_single_image_field(...):
    ...; assert fake_relay.requests[-1].image_field_names == ["image"]

@pytest.mark.asyncio
async def test_no_image_raises(fake_relay):            # relay returns 200 {"data": []}
    with pytest.raises(RuntimeError): ...

@pytest.mark.asyncio
async def test_http_error_raises_without_key(fake_relay):   # relay returns 500 {"error": "boom"}
    with pytest.raises(RuntimeError) as e: ...
    assert "500" in str(e.value) and "secret-key" not in str(e.value)
```

- [ ] **Step 2: 运行测试，确认失败**
- [ ] **Step 3: 实现 `image_client.py`**；可参考 `../astrbot_plugin_omnidraw/providers/openai_impl.py` 里 FormData 的写法
- [ ] **Step 4: 运行测试，确认通过；跑 ruff**
- [ ] **Step 5: 提交** `feat: add gpt-image client`

---

### Task 6: 插件主体与配置

**Files:**
- Create: `_conf_schema.json`
- Rewrite: `main.py`
- Create: `tests/test_main.py`

**Interfaces:**
- Consumes: 前面所有任务的接口。
- Produces: `class XavierPhone(Star)`
  - `__init__(self, context: Context, config: AstrBotConfig)`：`self.data_dir = StarTools.get_data_dir("astrbot_plugin_xavier_phone")`；`self.album = Album(self.data_dir / "album")`；`scenes_dir` 为空时取 `self.data_dir / "scenes"`。
  - `@filter.on_llm_request()` `async def inject_guide(self, event, req: ProviderRequest)`：`req.system_prompt += "\n\n" + build_guide(config["guide_prompt"] or DEFAULT_GUIDE, list_scenes(scenes_dir))`。
  - `@filter.on_decorating_result()` `async def render_markers(self, event: AstrMessageEvent)`
  - 模块常量 `MAX_MARKERS_PER_REPLY = 3`。

- [ ] **Step 1: 写 `_conf_schema.json`**

字段和默认值见 Global Constraints，另加 `api_key`（string，默认空）和 `guide_prompt`（text，默认空，hint 写“留空使用内置说明，`{scenes}` 会被替换为场景列表”）。每个字段都要有中文 `description` 和 `hint`，`max_reference_images` 的 hint 写明“中转站不支持多图参考时改为 1”。

- [ ] **Step 2: 写失败测试 `tests/test_main.py`**

构造方式：`XavierPhone(MagicMock(), config_dict)`，其中 `StarTools.get_data_dir` 用 monkeypatch 指向 `tmp_path`。用 monkeypatch 替换 `main.generate_image`，按描述返回 `b"IMG"`、抛异常或 `await asyncio.sleep(10)`。事件用一个简单的假对象，带 `get_result()` 和 `unified_msg_origin`；结果用 `MessageEventResult().message(text).set_result_content_type(ResultContentType.LLM_RESULT)`。

```python
@pytest.mark.asyncio
async def test_replaces_marker_in_place(plugin, make_event):
    ev = make_event("刚回来$[📷拍照·公寓-露台：橘猫]$你看")
    await plugin.render_markers(ev)
    chain = ev.get_result().chain
    assert [type(c).__name__ for c in chain] == ["Plain", "Image", "Plain"]
    assert chain[0].text == "刚回来$" and chain[2].text == "$你看"
    assert plugin.album.count_on(date.today()) == 1

@pytest.mark.asyncio
async def test_generation_error_falls_back(plugin, make_event):   # generate_image raises for "坏"
    ev = make_event("[📷拍照：坏][✏️涂鸦：好]")
    await plugin.render_markers(ev)
    chain = ev.get_result().chain
    assert chain[0].text == "[📷分享图片：坏]" and type(chain[1]).__name__ == "Image"

@pytest.mark.asyncio
async def test_timeout_falls_back(plugin_timeout_0_1s, make_event):   # generate_image sleeps 10s
    ev = make_event("a[📷拍照：慢]b")
    await plugin_timeout_0_1s.render_markers(ev)
    assert [c.text for c in ev.get_result().chain] == ["a[📷分享图片：慢]b"]

@pytest.mark.asyncio
async def test_cap_and_quota_fallback(plugin_limit_2, make_event):   # daily limit 2, one image already saved today
    ev = make_event("[📷拍照：1][📷拍照：2][📷拍照：3][📷拍照：4]")
    await plugin_limit_2.render_markers(ev)
    kinds = [type(c).__name__ for c in ev.get_result().chain]
    assert kinds == ["Image", "Plain"] and ev.get_result().chain[1].text == "[📷分享图片：2][📷分享图片：3][📷分享图片：4]"

@pytest.mark.asyncio
async def test_unconfigured_falls_back(plugin_no_key, make_event):
    ev = make_event("[✏️涂鸦：兔子]")
    await plugin_no_key.render_markers(ev)
    assert ev.get_result().chain[0].text == "[✏️涂鸦：兔子]"

@pytest.mark.asyncio
async def test_non_llm_result_untouched(plugin, make_event):
    ev = make_event("[📷拍照：猫]", llm=False)
    await plugin.render_markers(ev)
    assert ev.get_result().chain[0].text == "[📷拍照：猫]"

@pytest.mark.asyncio
async def test_scene_refs_passed(plugin_with_scenes, make_event, calls):   # scenes/公寓-露台/{白天.jpg,夜晚.jpg}
    await plugin_with_scenes.render_markers(make_event("[📷拍照·公寓-露台：猫]"))
    assert len(calls[-1]["refs"]) == 1
    await plugin_with_scenes.render_markers(make_event("[✏️涂鸦·公寓-露台：猫]"))
    assert calls[-1]["refs"] == []

@pytest.mark.asyncio
async def test_inject_guide(plugin_with_scenes):
    req = ProviderRequest(system_prompt="人设")
    await plugin_with_scenes.inject_guide(MagicMock(), req)
    assert req.system_prompt.startswith("人设\n\n") and "公寓-露台" in req.system_prompt
```

- [ ] **Step 3: 运行测试，确认失败**

- [ ] **Step 4: 实现 `main.py`**

`render_markers` 的流程（全部写在钩子里，可以有一个内部的 `async def run(marker)` 闭包）：

```
result = event.get_result(); 不是 LLM 结果或没有 chain 就 return
markers = 对每个 Plain 调用 parse_markers；一个都没有就 return
now = datetime.now()
budget = MAX_MARKERS_PER_REPLY
若启用每日上限：budget = min(budget, max(0, daily_limit - album.count_on(now.date())))
若 base_url/api_key/model 有一个为空：budget = 0
按全局出现顺序，前 budget 个标记去生成，其余直接用回退文字
生成：每个标记先 refs = pick_refs(...)（涂鸦为 []），再 prompt = build_prompt(...)，
     然后 asyncio.wait_for(generate_image(...), timeout_seconds)，最后 album.save(...) 得到 Path；
     元数据为 kind/scene/description/prompt/refs(文件名)/session
所有标记用一次 asyncio.gather(return_exceptions=True) 并发；异常用 logger.warning 记录后视为失败
重建消息链：标记前后的文字和失败标记的回退文字拼进同一个 Plain 缓冲区，
     成功的标记先输出缓冲区（非空时）再输出 Image.fromFileSystem(path)；非 Plain 组件原样保留
最后一次性赋值 result.chain = new_chain
```

aiohttp session：在 `__init__` 中设 `self._session = None`，第一次用到时创建，在 `terminate()` 里关闭。

- [ ] **Step 5: 运行全部测试，确认通过；跑 ruff**
- [ ] **Step 6: 提交** `feat: render camera and doodle markers into images`

---

### Task 7: README、真机验证与推送

**Files:**
- Rewrite: `README.md`（中文。内容包括：功能、三种标记、场景库目录结构和白天/夜晚命名规则、配置项说明、`max_reference_images` 的说明）

- [ ] **Step 1: 写 README，提交** `docs: add README`
- [ ] **Step 2: 实测中转站是否支持多图参考**

用户在 AstrBot 插件配置里填好 api_key。然后用一次性脚本调用 `generate_image`，传入 `公寓-客厅` 的白天和全景两张图。如果报错或明显只用了一张图，告诉用户把 `max_reference_images` 设为 1。在 README 里记下实测结论。

- [ ] **Step 3: 配置场景库**

把用户的场景参考图目录填进 `scenes_dir`，或者经用户同意后复制到数据目录的 `scenes/`。

- [ ] **Step 4: 端到端验证**

重载插件后，在 QQ 上和沈星回聊天，分别引导出这几种情况：带场景的拍照、自由场景的拍照、涂鸦、一次失败（比如临时填一个错误的 key）。确认以下几点：
- 图片出现在对应的 `$` 片段之间；
- 失败时显示回退文字；
- 画面里没有人脸和手；
- `album.jsonl` 有记录。

- [ ] **Step 5: 推送前征求用户同意**，再执行 `git push origin master`。
