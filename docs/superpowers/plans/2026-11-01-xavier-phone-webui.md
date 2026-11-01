# 小手机前端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在插件内起一个带密码登录的独立网页服务（默认 1850 端口），提供仿 iPhone 液态玻璃风格的相册、画板、设置三个 App。

**Architecture:** 后端分三层：`webui/auth.py` 负责登录与防暴力破解，`webui/library.py` 负责照片列表、收藏、自建相册、缩略图和删除（基于现有 `Album`），`webui/server.py` 用 aiohttp.web 暴露 JSON 接口和静态页面。前端是 `webui/static/` 下不需要构建的 `index.html` + `app.js` + `style.css`。插件在 `initialize()` 中启动服务、在 `terminate()` 中停止，启动失败只记日志。

**Tech Stack:** aiohttp.web（AstrBot 核心依赖）、Pillow、原生 JS/CSS；测试使用 pytest、pytest-asyncio、`aiohttp.test_utils`。

**Spec:** `docs/superpowers/specs/2026-11-01-xavier-phone-webui-design.md`

## Global Constraints

- 路径相对插件目录 `D:\Software\AstrBot-master\data\plugins\astrbot_plugin_glimpse`，分支 `feat/v0.1`。
- 测试在 AstrBot 根目录运行：`uv run --no-sync python -m pytest data/plugins/astrbot_plugin_glimpse/tests -q -p no:warnings`；导入用 `data.plugins.astrbot_plugin_glimpse.<module>`；异步测试加 `@pytest.mark.asyncio`。
- 每个任务结束前在插件目录运行 `uv run --no-sync ruff format . && uv run --no-sync ruff check .` 并通过。
- 提交信息使用 conventional commits，并以 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` 结尾。
- 不新增 Python 依赖；前端不引用任何 CDN。
- 遵守 AGENTS.md：`pathlib`；注释和日志用英文；Google 风格 docstring；KISS。
- 数据目录 = 插件的 `self.data_dir`。具体文件：`album/library.json`、`album/thumbs/`、`webui/auth.json`、`webui/settings.json`、`webui/wallpapers/`。
- 配置值：`webui_config.enabled=true`、`host` 选项为 `127.0.0.1`/`0.0.0.0`（默认 `127.0.0.1`）、`port=1850`。
- 安全参数：PBKDF2-SHA256 迭代 200000 次；密码至少 8 位；6 位数字设置码；每次校验失败延迟 1 秒；10 分钟内失败 10 次则暂停 10 分钟；cookie 名 `xp_session`，有效期 7 天，HttpOnly，SameSite=Lax，HTTPS 下（或请求头 `X-Forwarded-Proto: https`）加 Secure。
- 缩略图：长边 480px，JPEG 质量 80。上传壁纸上限 10MB，校验后转成 JPEG 保存。
- 内置壁纸 id：`starry`、`mist`、`apricot`、`night`；默认壁纸 `starry`；默认主题色 `#7aa7ff`。
- `Album.save()` 和 `Album.delete()` 都在事件循环上同步执行，**不得**放进线程。

## Review Focus

1. **端口被占用或服务启动失败**：插件照常加载，生图功能不受影响。测试见 Task 5 的 `test_initialize_survives_port_in_use`。
2. **文件名包含 `../`、`..\`，或不在相册记录里**：图片、收藏、删除接口一律返回 404，不碰磁盘上的其他文件。测试见 Task 4 的 `test_image_rejects_unknown_and_traversal`。
3. **删除一张已收藏、已加入相册、已生成缩略图的照片**：这些引用全部清理干净，相册记录也同步删除。测试见 Task 3 的 `test_delete_cascades`。
4. **记录还在但图片文件已被手动删除**：列表照常返回；取原图返回 404；取缩略图不会崩溃，同样返回 404。测试见 Task 3 的 `test_missing_file_thumbnail_none` 和 Task 4 的 `test_image_missing_file_404`。
5. **上传的壁纸不是图片，或超过 10MB**：返回 400，不保存任何文件。测试见 Task 4 的 `test_wallpaper_upload_validation`。

---

### Task 1: Album 读取全部记录与删除

**Files:**
- Modify: `album.py`
- Test: `tests/test_album.py`

**Interfaces:**
- Produces:
  - `Album.records(self) -> list[dict]`：按文件顺序返回所有有效记录，跳过坏行。
  - `Album.delete(self, file: str) -> bool`：删除图片文件，并把对应记录从 `album.jsonl` 中移除（写入 `album.jsonl.tmp` 后用 `Path.replace` 原子替换）；找不到记录时返回 False。

- [ ] **Step 1: 写失败测试**

```python
def test_records_and_delete(tmp_path):
    album = Album(tmp_path)
    a = album.save(b"A", {"kind": "photo", "description": "猫"})
    b = album.save(b"B", {"kind": "doodle", "description": "兔"})
    assert [r["file"] for r in album.records()] == [a.name, b.name]
    assert album.delete(a.name) is True
    assert not a.exists() and [r["file"] for r in album.records()] == [b.name]
    assert album.delete("nope.png") is False
    assert album.count_on(date.today()) == 1

def test_delete_when_image_already_gone(tmp_path):
    album = Album(tmp_path)
    a = album.save(b"A", {"kind": "photo"})
    a.unlink()
    assert album.delete(a.name) is True and album.records() == []
```

- [ ] **Step 2: 运行测试，确认失败**
- [ ] **Step 3: 实现两个方法**
- [ ] **Step 4: 运行全部测试，确认通过；跑 ruff**
- [ ] **Step 5: 提交** `feat: add album records and delete`

---

### Task 2: 登录与防暴力破解

**Files:**
- Create: `webui/__init__.py`（空文件）、`webui/auth.py`
- Test: `tests/test_webui_auth.py`

**Interfaces:**
- Produces: `class AuthStore`
  - `__init__(self, path: Path, clock: Callable[[], float] = time.time)`：从 `path`（即 `webui/auth.json`）读取 `{"salt", "hash"}`；尚未设置密码时生成 `self.setup_code`（6 位数字字符串），否则为 `None`。
  - `is_set: bool`（property）
  - `locked_seconds(self) -> int`：仍在暂停期时返回剩余秒数，否则返回 0。
  - `setup(self, code: str, password: str) -> str`：成功返回会话 token。设置码错误时抛 `PermissionError`；密码不足 8 位时抛 `ValueError`；已经设置过或处于暂停期时抛 `PermissionError`。
  - `login(self, password: str) -> str | None`
  - `validate(self, token: str | None) -> bool`
  - `logout(self, token: str | None) -> None`
  - `change(self, old: str, new: str) -> bool`：新密码不足 8 位时抛 `ValueError`。
  - 失败计数：用 `clock()` 记录最近的失败时间戳；10 分钟（600 秒）窗口内达到 10 次后，暂停 600 秒。1 秒延迟由服务端负责（Task 4），这里不 sleep。
  - 会话：`dict[token, expires_at]` 存在内存里，有效期 7 天；token 用 `secrets.token_urlsafe(32)`。

- [ ] **Step 1: 写失败测试**

```python
def test_setup_requires_code_and_length(tmp_path):
    store = AuthStore(tmp_path / "auth.json")
    assert not store.is_set and len(store.setup_code) == 6 and store.setup_code.isdigit()
    with pytest.raises(PermissionError):
        store.setup("000000" if store.setup_code != "000000" else "111111", "password1")
    with pytest.raises(ValueError):
        store.setup(store.setup_code, "short")
    token = store.setup(store.setup_code, "password1")
    assert store.is_set and store.validate(token) and store.setup_code is None
    data = json.loads((tmp_path / "auth.json").read_text(encoding="utf-8"))
    assert "password1" not in json.dumps(data) and set(data) >= {"salt", "hash"}

def test_login_logout_change_and_persist(tmp_path):
    store = AuthStore(tmp_path / "auth.json")
    store.setup(store.setup_code, "password1")
    reloaded = AuthStore(tmp_path / "auth.json")
    assert reloaded.is_set and reloaded.setup_code is None
    token = reloaded.login("password1")
    assert token and reloaded.login("wrong-pass") is None
    reloaded.logout(token)
    assert not reloaded.validate(token)
    assert reloaded.change("password1", "password2") is True
    assert reloaded.login("password2")

def test_lockout_after_ten_failures(tmp_path):
    now = [1000.0]
    store = AuthStore(tmp_path / "auth.json", clock=lambda: now[0])
    store.setup(store.setup_code, "password1")
    for _ in range(10):
        assert store.login("bad-password") is None
    assert store.locked_seconds() == 600
    assert store.login("password1") is None
    now[0] += 601
    assert store.locked_seconds() == 0 and store.login("password1")

def test_session_expires(tmp_path):
    now = [0.0]
    store = AuthStore(tmp_path / "auth.json", clock=lambda: now[0])
    token = store.setup(store.setup_code, "password1")
    now[0] += 7 * 86400 + 1
    assert not store.validate(token)
```

- [ ] **Step 2: 运行测试，确认失败**
- [ ] **Step 3: 实现 `webui/auth.py`**：用 `hashlib.pbkdf2_hmac("sha256", pw, salt, 200000)` 计算哈希，`hmac.compare_digest` 比较。
- [ ] **Step 4: 运行测试，确认通过；跑 ruff**
- [ ] **Step 5: 提交** `feat: add web UI auth store`

---

### Task 3: 照片库（列表、收藏、相册、缩略图、删除）

**Files:**
- Create: `webui/library.py`
- Test: `tests/test_webui_library.py`

**Interfaces:**
- Consumes: Task 1 的 `Album.records()` 和 `Album.delete()`。
- Produces: `class Library`
  - `__init__(self, album: Album)`：整理信息存放在 `album.root / "library.json"`，缩略图存放在 `album.root / "thumbs"`。
  - `has(self, file: str) -> bool`：`file` 是否为 `records()` 里的某个文件名。
  - `list_photos(self, app: str, view: str) -> list[dict]`：`app` 为 `"album"` 时取 kind 是 photo 或 film 的记录，为 `"doodle"` 时只取 doodle；`view` 为 `"all"`、`"favorites"` 或某个相册 id。按 `created_at` 倒序。每项为 `{file, kind, scene, description, created_at, favorite: bool, albums: [id]}`。`view` 是未知的相册 id 时返回 `[]`。
  - `set_favorite(self, file: str, value: bool) -> None`
  - `albums(self) -> list[dict]`：每项为 `{id, name, count}`。
  - `create_album(self, name: str) -> dict`：id 用 `uuid4().hex[:8]`；去掉首尾空格后为空时抛 `ValueError`。
  - `rename_album(self, album_id: str, name: str) -> bool`
  - `delete_album(self, album_id: str) -> bool`
  - `set_in_album(self, album_id: str, file: str, add: bool) -> bool`
  - `delete(self, file: str) -> bool`：依次调用 `album.delete`、把它从收藏和所有相册中移除、删除缩略图。
  - `thumbnail(self, file: str) -> Path | None`：缩略图不存在时生成（长边 480px，JPEG 质量 80，先 `exif_transpose` 再转 RGB）；原图缺失或无法读取时返回 None。
  - 所有写 `library.json` 的操作都是：读出、修改、整体写回（`ensure_ascii=False`）。

- [ ] **Step 1: 写失败测试**

```python
@pytest.fixture
def lib(tmp_path):
    album = Album(tmp_path / "album")
    files = {
        "p": album.save(png(800, 600), {"kind": "photo", "scene": "公寓-客厅", "description": "猫"}).name,
        "f": album.save(png(600, 400), {"kind": "film", "scene": "", "description": "海"}).name,
        "d": album.save(png(300, 300), {"kind": "doodle", "scene": "", "description": "兔"}).name,
    }
    return Library(album), files

def test_list_by_app_newest_first(lib):
    library, f = lib
    assert {p["file"] for p in library.list_photos("album", "all")} == {f["p"], f["f"]}
    assert [p["file"] for p in library.list_photos("doodle", "all")] == [f["d"]]

def test_favorites_and_albums(lib):
    library, f = lib
    library.set_favorite(f["p"], True)
    assert [p["file"] for p in library.list_photos("album", "favorites")] == [f["p"]]
    a = library.create_album("海边")
    assert library.set_in_album(a["id"], f["f"], True)
    assert [p["file"] for p in library.list_photos("album", a["id"])] == [f["f"]]
    assert library.albums() == [{"id": a["id"], "name": "海边", "count": 1}]
    assert library.rename_album(a["id"], "去海边") and library.albums()[0]["name"] == "去海边"
    assert library.delete_album(a["id"]) and library.list_photos("album", a["id"]) == []
    with pytest.raises(ValueError):
        library.create_album("  ")

def test_delete_cascades(lib):
    library, f = lib
    a = library.create_album("x")
    library.set_in_album(a["id"], f["p"], True)
    library.set_favorite(f["p"], True)
    thumb = library.thumbnail(f["p"])
    assert thumb.exists() and Image.open(thumb).size == (480, 360)
    assert library.delete(f["p"])
    assert not thumb.exists() and not library.has(f["p"])
    assert library.albums()[0]["count"] == 0
    assert library.list_photos("album", "favorites") == []

def test_missing_file_thumbnail_none(lib):
    library, f = lib
    (library.album.root / f["d"]).unlink()
    assert library.thumbnail(f["d"]) is None
    assert [p["file"] for p in library.list_photos("doodle", "all")] == [f["d"]]
```

- [ ] **Step 2: 运行测试，确认失败**
- [ ] **Step 3: 实现 `webui/library.py`**
- [ ] **Step 4: 运行测试，确认通过；跑 ruff**
- [ ] **Step 5: 提交** `feat: add photo library for the web UI`

---

### Task 4: 网页服务与接口

**Files:**
- Create: `webui/server.py`；`webui/static/index.html` 先放一个最小占位页（Task 6 再重写）。
- Test: `tests/test_webui_server.py`

**Interfaces:**
- Consumes: Task 2 的 `AuthStore`、Task 3 的 `Library`。
- Produces: `class PhoneServer`
  - `__init__(self, data_dir: Path, album: Album)`：创建 `AuthStore(data_dir / "webui" / "auth.json")`、`Library(album)`；设置文件为 `data_dir / "webui" / "settings.json"`，壁纸目录为 `data_dir / "webui" / "wallpapers"`。
  - `build_app(self) -> web.Application`
  - `async start(self, host: str, port: int) -> None`：使用 `web.AppRunner` 和 `web.TCPSite`；设置码存在时打印日志 `[glimpse] Phone web UI setup code: 123456`。
  - `async stop(self) -> None`
- 路由按设计文档 7.6 实现。认证中间件：路径以 `/api/` 开头、且不在 `/api/auth/` 下的请求，都需要有效的 `xp_session` cookie，否则返回 401 `{"error": "auth required"}`。
- `POST /api/auth/setup` 的请求体为 `{code, password}`，`/login` 为 `{password}`，`/password` 为 `{old, new}`。校验失败时先 `await asyncio.sleep(self.fail_delay)`（默认 1.0，测试中设为 0）再返回 403；处于暂停期时返回 429 `{"error": "locked", "seconds": n}`；密码过短返回 400。
- `GET /api/auth/status` 返回 `{set, authenticated, locked_seconds}`。
- `GET /api/settings` 返回 `{wallpaper, accent}`，默认为 `{"wallpaper": "starry", "accent": "#7aa7ff"}`；`POST` 时校验 `accent` 匹配 `^#[0-9a-fA-F]{6}$`，`wallpaper` 必须是内置 id 或已上传的文件名，否则返回 400。
- `POST /api/wallpaper`：使用 multipart 字段 `file`，超过 10MB 或 Pillow 无法打开时返回 400；成功后保存为 `<uuid8>.jpg`，返回 `{name}`。
- `GET /api/image/{file}`：`library.has(file)` 为假时返回 404；带 `?thumb=1` 时返回缩略图（为 None 时返回 404）；原图文件不存在时返回 404。

- [ ] **Step 1: 写失败测试**（`aiohttp.test_utils.TestClient` + `TestServer`，`server.fail_delay = 0`）

```python
async def login(client, server):
    r = await client.post("/api/auth/setup", json={"code": server.auth.setup_code, "password": "password1"})
    assert r.status == 200

@pytest.mark.asyncio
async def test_auth_required_and_flow(client, server):
    assert (await client.get("/api/photos?app=album&view=all")).status == 401
    status = await (await client.get("/api/auth/status")).json()
    assert status == {"set": False, "authenticated": False, "locked_seconds": 0}
    assert (await client.post("/api/auth/setup", json={"code": "x", "password": "password1"})).status == 403
    await login(client, server)
    assert (await client.get("/api/photos?app=album&view=all")).status == 200

@pytest.mark.asyncio
async def test_secure_cookie_behind_https_proxy(client, server):
    r = await client.post("/api/auth/setup", json={"code": server.auth.setup_code, "password": "password1"},
                          headers={"X-Forwarded-Proto": "https"})
    assert "Secure" in r.headers["Set-Cookie"] and "HttpOnly" in r.headers["Set-Cookie"]

@pytest.mark.asyncio
async def test_image_rejects_unknown_and_traversal(client, server, files):
    await login(client, server)
    for bad in ("nope.png", "..%2F..%2Fauth.json", "..%5Cauth.json"):
        assert (await client.get(f"/api/image/{bad}")).status == 404
        assert (await client.delete(f"/api/photos/{bad}")).status == 404

@pytest.mark.asyncio
async def test_image_missing_file_404(client, server, files):
    await login(client, server)
    (server.library.album.root / files["p"]).unlink()
    assert (await client.get(f"/api/image/{files['p']}")).status == 404
    assert (await client.get(f"/api/image/{files['p']}?thumb=1")).status == 404

@pytest.mark.asyncio
async def test_photo_actions(client, server, files):
    await login(client, server)
    assert (await client.post(f"/api/photos/{files['p']}/favorite", json={"value": True})).status == 200
    fav = await (await client.get("/api/photos?app=album&view=favorites")).json()
    assert [p["file"] for p in fav["photos"]] == [files["p"]]
    a = await (await client.post("/api/albums", json={"name": "海边"})).json()
    assert (await client.post(f"/api/albums/{a['id']}/photos", json={"file": files["p"], "add": True})).status == 200
    assert (await client.delete(f"/api/photos/{files['p']}")).status == 200
    assert (await (await client.get("/api/albums")).json())["albums"][0]["count"] == 0

@pytest.mark.asyncio
async def test_wallpaper_upload_validation(client, server):
    await login(client, server)
    bad = aiohttp.FormData(); bad.add_field("file", b"not image", filename="x.jpg")
    assert (await client.post("/api/wallpaper", data=bad)).status == 400
    big = aiohttp.FormData(); big.add_field("file", b"0" * (10 * 1024 * 1024 + 1), filename="big.jpg")
    assert (await client.post("/api/wallpaper", data=big)).status == 400
    assert not any((server.data_dir / "webui" / "wallpapers").glob("*"))
    ok = aiohttp.FormData(); ok.add_field("file", png(100, 200), filename="w.png")
    name = (await (await client.post("/api/wallpaper", data=ok)).json())["name"]
    assert (await client.post("/api/settings", json={"wallpaper": name, "accent": "#112233"})).status == 200
    assert (await client.post("/api/settings", json={"wallpaper": "../x", "accent": "#112233"})).status == 400
    assert (await client.get(f"/api/wallpaper/{name}")).status == 200

@pytest.mark.asyncio
async def test_lockout_returns_429(client, server):
    await login(client, server)
    await client.post("/api/auth/logout")
    for _ in range(10):
        await client.post("/api/auth/login", json={"password": "bad-password"})
    r = await client.post("/api/auth/login", json={"password": "password1"})
    assert r.status == 429 and (await r.json())["seconds"] > 0
```

- [ ] **Step 2: 运行测试，确认失败**
- [ ] **Step 3: 实现 `webui/server.py`**：上传大小用 `web.Application(client_max_size=10 * 1024 * 1024 + 4096)` 限制，再自行检查文件字节数；超限时 aiohttp 会抛 `HTTPRequestEntityTooLarge`，捕获后统一返回 400。静态文件用 `app.router.add_static("/static", static_dir)`，`/` 直接返回 `index.html`。
- [ ] **Step 4: 运行测试，确认通过；跑 ruff**
- [ ] **Step 5: 提交** `feat: add phone web UI server and API`

---

### Task 5: 接入插件与配置

**Files:**
- Modify: `main.py`（新增 `initialize`，扩展 `terminate`）、`_conf_schema.json`（在最前面新增 `webui_config`）
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: Task 4 的 `PhoneServer`。
- Produces: `Glimpse.phone_server: PhoneServer | None`；`async initialize(self) -> None`。

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.asyncio
async def test_initialize_starts_and_terminate_stops(make_plugin, unused_tcp_port):
    plugin = make_plugin(port=unused_tcp_port)
    await plugin.initialize()
    assert plugin.phone_server is not None
    async with aiohttp.ClientSession() as s:
        assert (await s.get(f"http://127.0.0.1:{unused_tcp_port}/api/auth/status")).status == 200
    await plugin.terminate()

@pytest.mark.asyncio
async def test_initialize_survives_port_in_use(make_plugin, unused_tcp_port):
    blocker = socket.socket(); blocker.bind(("127.0.0.1", unused_tcp_port)); blocker.listen()
    try:
        plugin = make_plugin(port=unused_tcp_port)
        await plugin.initialize()          # must not raise
        assert plugin.phone_server is None
    finally:
        blocker.close()

@pytest.mark.asyncio
async def test_webui_disabled(make_plugin):
    plugin = make_plugin(enabled=False)
    await plugin.initialize()
    assert plugin.phone_server is None
```

（`unused_tcp_port` 自己写成一个 fixture：绑定 `("127.0.0.1", 0)` 拿到端口后关闭；`GROUP_OF` 会通过 schema 自动把 `port`、`enabled` 路由到 `webui_config`。）

- [ ] **Step 2: 运行测试，确认失败**
- [ ] **Step 3: 实现**：在 schema 里新增 `webui_config`（描述“小手机”，字段见 Global Constraints，`host` 带 options 和提示）。`initialize()` 读取配置后启动服务；任何异常都 `logger.error` 并把 `phone_server` 设为 None。`terminate()` 先停止服务，再关闭 HTTP 会话。
- [ ] **Step 4: 运行全部测试，确认通过；跑 ruff**
- [ ] **Step 5: 提交** `feat: start the phone web UI with the plugin`

---

### Task 6: 前端（主屏、相册、画板、设置）

**Files:**
- Rewrite: `webui/static/index.html`
- Create: `webui/static/app.js`、`webui/static/style.css`

**Interfaces:**
- Consumes: Task 4 的全部接口（使用 `fetch`，`credentials: "same-origin"`）。

- [ ] **Step 1: 实现页面结构与登录**：未登录时显示液态玻璃登录卡片，使用内置 `starry` 渐变壁纸。未设置密码时显示“设置码 + 新密码 + 确认密码”，并提示“设置码在 AstrBot 控制台日志里”；暂停期显示剩余秒数。
- [ ] **Step 2: 主屏**：状态栏实时显示时间（每 30 秒刷新一次）；App 网格和 Dock 都放相册、画板、设置；液态玻璃使用 `backdrop-filter: blur() saturate()`、半透明渐变和内高光描边，并用 `@supports not (backdrop-filter: blur(1px))` 做退化。主题色写入 CSS 变量 `--accent`。手机上铺满屏幕并使用 `env(safe-area-inset-*)`；在 `min-width: 600px` 时居中显示 390×844 的手机框。
- [ ] **Step 3: 相册与画板**：使用同一个网格组件，缩略图取 `/api/image/{file}?thumb=1`，带 `loading="lazy"`；胶片缩略图显示胶卷角标。相册顶部是分段控件「全部 / 收藏 / 相册」，相册列表支持新建、改名、删除（用 `prompt`/`confirm` 或液态玻璃弹窗）。画板只有「全部 / 收藏」。
- [ ] **Step 4: 查看器**：全屏黑底；支持左右滑动（pointer 事件）和键盘左右键；单击切换操作栏的显示；操作栏为 ♡、添加到相册（仅相册 App）、ⓘ、🗑。信息抽屉显示描述、`YYYY年M月D日 HH:mm` 格式的时间，以及地点（为空时不显示）。删除前先确认，删除后自动跳到下一张。
- [ ] **Step 5: 设置**：iOS 风格分组列表，包含墙纸（四款内置渐变 + 上传）、主题色（预设色块 + `<input type="color">`）、修改密码、退出登录。
- [ ] **Step 6: 浏览器验证**：启动插件服务，在浏览器中按 375×812 和桌面尺寸各走一遍：设置密码 → 浏览相册和画板 → 收藏 → 加入相册 → 查看信息 → 删除 → 换壁纸和主题色 → 退出后重新登录。另外确认控制台没有报错。
- [ ] **Step 7: 提交** `feat: add liquid-glass phone front end`

---

### Task 7: README 与收尾

**Files:**
- Modify: `README.md`

- [ ] **Step 1: README 新增「小手机」一节**，包含：如何打开（`http://服务器IP:1850`，监听地址改为 `0.0.0.0`）、首次设置密码要用 AstrBot 日志里的设置码、忘记密码时删除 `webui/auth.json` 并重载插件、防暴力破解规则、上公网时建议加 HTTPS，并附一段 Caddy 示例：

```text
phone.example.com {
    reverse_proxy 127.0.0.1:1850
}
```

- [ ] **Step 2: 运行全部测试并跑 ruff，提交** `docs: document the phone web UI`
