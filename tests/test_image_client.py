import base64
from dataclasses import dataclass, field

import aiohttp
import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestServer

from data.plugins.astrbot_plugin_xavier_phone.image_client import generate_image


@dataclass
class Seen:
    path: str
    headers: dict
    json: dict | None = None
    image_field_names: list = field(default_factory=list)


@dataclass
class FakeRelay:
    session: aiohttp.ClientSession
    base_url: str
    requests: list
    mode: dict


@pytest_asyncio.fixture
async def fake_relay():
    requests: list[Seen] = []
    mode = {"reply": "b64"}

    async def images(request: web.Request):
        seen = Seen(request.path, dict(request.headers))
        if request.content_type == "application/json":
            seen.json = await request.json()
        else:
            reader = await request.multipart()
            async for part in reader:
                if part.name.startswith("image"):
                    seen.image_field_names.append(part.name)
                await part.read()
        requests.append(seen)
        if mode["reply"] == "b64":
            return web.json_response({"data": [{"b64_json": base64.b64encode(b"IMG").decode()}]})
        if mode["reply"] == "url":
            return web.json_response({"data": [{"url": str(request.url.with_path("/file.png"))}]})
        if mode["reply"] == "empty":
            return web.json_response({"data": []})
        return web.json_response({"error": "boom"}, status=500)

    async def file(request: web.Request):
        requests.append(Seen(request.path, dict(request.headers)))
        return web.Response(body=b"URLIMG")

    app = web.Application()
    app.router.add_post("/v1/images/generations", images)
    app.router.add_post("/v1/images/edits", images)
    app.router.add_get("/file.png", file)
    server = TestServer(app)
    await server.start_server()
    async with aiohttp.ClientSession() as session:
        yield FakeRelay(session, str(server.make_url("/v1/")), requests, mode)
    await server.close()


async def call(relay, refs=(), key="k"):
    return await generate_image(
        relay.session, relay.base_url, key, "gpt-image-2.5", "p", "1024x1536", list(refs)
    )


@pytest.mark.asyncio
async def test_generations_b64(fake_relay):
    assert await call(fake_relay) == b"IMG"
    req = fake_relay.requests[-1]
    assert req.path == "/v1/images/generations"
    assert req.json == {"model": "gpt-image-2.5", "prompt": "p", "size": "1024x1536", "n": 1}
    assert req.headers["Authorization"] == "Bearer k"


@pytest.mark.asyncio
async def test_edits_multi_image_and_url(fake_relay, tmp_path):
    a, b = ("白天.png", b"A"), ("全景.png", b"B")
    fake_relay.mode["reply"] = "url"
    assert await call(fake_relay, [a, b]) == b"URLIMG"
    assert fake_relay.requests[-2].path == "/v1/images/edits"
    assert fake_relay.requests[-2].image_field_names == ["image[]", "image[]"]


@pytest.mark.asyncio
async def test_edits_single_image_field(fake_relay, tmp_path):
    a = ("a.png", b"A")
    assert await call(fake_relay, [a]) == b"IMG"
    assert fake_relay.requests[-1].image_field_names == ["image"]


@pytest.mark.asyncio
async def test_no_image_raises(fake_relay):
    fake_relay.mode["reply"] = "empty"
    with pytest.raises(RuntimeError):
        await call(fake_relay)


@pytest.mark.asyncio
async def test_http_error_raises_without_key(fake_relay):
    fake_relay.mode["reply"] = "error"
    with pytest.raises(RuntimeError) as e:
        await call(fake_relay, key="secret-key")
    assert "500" in str(e.value) and "secret-key" not in str(e.value)

