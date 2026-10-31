"""Minimal client for an OpenAI-compatible gpt-image relay."""

import base64
import mimetypes

import aiohttp


async def generate_image(
    session: aiohttp.ClientSession,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    size: str,
    refs: list[tuple[str, bytes]],
) -> bytes:
    """Generate one image, using /images/edits when reference images are given.

    Args:
        session: Shared aiohttp session.
        base_url: Relay base URL, e.g. https://api.example.com/v1.
        api_key: Relay API key.
        model: Image model name.
        prompt: Full image prompt.
        size: Image size such as "1024x1536".
        refs: Reference images as (filename, bytes); empty for text-to-image.

    Returns:
        The generated image bytes.

    Raises:
        RuntimeError: If the relay returns an error status or no image.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    base = base_url.rstrip("/")
    if refs:
        form = aiohttp.FormData()
        for name, value in (
            ("model", model),
            ("prompt", prompt),
            ("size", size),
            ("n", "1"),
        ):
            form.add_field(name, value)
        field_name = "image[]" if len(refs) > 1 else "image"
        for filename, data in refs:
            form.add_field(
                field_name,
                data,
                filename=filename,
                content_type=mimetypes.guess_type(filename)[0] or "image/png",
            )
        request = session.post(f"{base}/images/edits", data=form, headers=headers)
    else:
        payload = {"model": model, "prompt": prompt, "size": size, "n": 1}
        request = session.post(
            f"{base}/images/generations", json=payload, headers=headers
        )

    async with request as resp:
        if resp.status >= 400:
            body = (await resp.text())[:200]
            raise RuntimeError(f"Image relay returned HTTP {resp.status}: {body}")
        data = await resp.json(content_type=None)

    items = data.get("data") if isinstance(data, dict) else None
    item = items[0] if items else {}
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if item.get("url"):
        async with session.get(item["url"]) as resp:
            if resp.status >= 400:
                raise RuntimeError(f"Image download returned HTTP {resp.status}")
            return await resp.read()
    raise RuntimeError("Image relay returned no image")
