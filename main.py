"""Xavier's phone: turn camera / film / doodle markers in his replies into images."""

import asyncio
import json
import re
import uuid
from datetime import datetime
from pathlib import Path

import aiohttp

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Image, Plain
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, StarTools

from .album import Album
from .image_client import generate_image
from .imaging import crop_to_ratio, prepare_reference, size_for_ratio
from .markers import fallback_text, parse_markers, parse_outfit_changes
from .prompts import DEFAULT_GUIDE, build_guide, build_prompt, resolve_prompts
from .scenes import (
    first_image,
    folder_images,
    list_scenes,
    match_objects,
    next_category_change,
    pick_outfit,
    pick_refs,
    wardrobe,
)

PLUGIN_NAME = "astrbot_plugin_glimpse"
MAX_MARKERS_PER_REPLY = 3
NODE_KEYS = ("base_url", "api_key", "model")
DEFAULT_GUARD_KEYWORDS = "自拍,镜子,镜中,对镜,合照,出镜,我的脸"
DEFAULT_RATIOS = {"photo": "3:4", "film": "3:2", "doodle": "1:1"}
# Words meaning his hand is in the shot (holding or touching something); a
# bare "手" would also match "手机", and "手指" would match "手指饼干".
HAND_WORDS = (
    "我的手",
    "手里",
    "我手上",
    "手中",
    "双手",
    "拿着",
    "捏着",
    "握着",
    "端着",
    "捧着",
    "举着",
    "摸着",
    "牵着",
    "指尖",
    "掌心",
    "袖子",
    "袖口",
    "胳膊",
    "手臂",
)


class Glimpse(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.data_dir = Path(StarTools.get_data_dir(PLUGIN_NAME))
        self.album = Album(self.data_dir / "album")
        lib = config.get("library_config") or {}
        self.dirs = {}
        for name in ("scenes", "objects", "outfits", "hands"):
            custom = str(lib.get(f"{name}_dir", "") or "").strip()
            if custom:
                self.dirs[name] = Path(custom)
            else:
                # Create the default folder so users can find where to put images.
                self.dirs[name] = self.data_dir / name
                self.dirs[name].mkdir(parents=True, exist_ok=True)
        self.override_path = self.data_dir / "outfit_override.json"
        self._session: aiohttp.ClientSession | None = None

    def _schedule(self) -> tuple[tuple[int, int], tuple[int, int]]:
        sched = self.config.get("schedule_config") or {}
        return (
            (int(sched.get("work_start_hour", 9)), int(sched.get("work_end_hour", 18))),
            (
                int(sched.get("sleep_start_hour", 23)),
                int(sched.get("sleep_end_hour", 7)),
            ),
        )

    def _current_outfit(self, now: datetime) -> str:
        """Return his outfit now: a still-valid change he made, else the schedule's."""
        try:
            override = json.loads(self.override_path.read_text(encoding="utf-8"))
            if datetime.fromisoformat(override["until"]) > now and override[
                "outfit"
            ] in list_scenes(self.dirs["outfits"]):
                return override["outfit"]
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return pick_outfit(self.dirs["outfits"], now, *self._schedule())

    @filter.on_llm_request()
    async def inject_guide(self, event: AstrMessageEvent, req: ProviderRequest):
        """Append the marker usage guide to the system prompt."""
        guide_cfg = self.config.get("guide_config") or {}
        if not guide_cfg.get("enable_guide", True):
            return
        photo_cfg = self.config.get("photo_config") or {}
        now = datetime.now()
        guide = build_guide(
            guide_cfg.get("guide_prompt") or DEFAULT_GUIDE,
            list_scenes(self.dirs["scenes"]),
            list_scenes(self.dirs["objects"]),
            self._current_outfit(now),
            bool(photo_cfg.get("allow_hands", False)),
            wardrobe(self.dirs["outfits"], now, *self._schedule()),
            self.config.get("prompt_config"),
        )
        req.system_prompt = f"{req.system_prompt or ''}\n\n{guide}"

    @filter.on_decorating_result()
    async def render_markers(self, event: AstrMessageEvent):
        """Replace markers in an LLM reply with generated images before sending.

        Images are generated first and the whole chain is swapped in one
        assignment, so the user gets text and images together. Any marker that
        is over budget, fails or times out is shown as its text fallback.
        """
        result = event.get_result()
        if result is None or not result.chain or not result.is_llm_result():
            return
        now = datetime.now()
        # Outfit changes are invisible: remember the last valid one until the
        # next schedule change, and strip every change marker from the text.
        for comp in result.chain:
            if not isinstance(comp, Plain):
                continue
            changes = parse_outfit_changes(comp.text)
            for _, _, name in changes:
                if name in list_scenes(self.dirs["outfits"]):
                    until = next_category_change(now, *self._schedule())
                    try:
                        self.override_path.write_text(
                            json.dumps(
                                {"outfit": name, "until": until.isoformat()},
                                ensure_ascii=False,
                            ),
                            encoding="utf-8",
                        )
                    except OSError as exc:
                        logger.warning(f"[glimpse] save outfit failed: {exc!r}")
            for start, end, _ in reversed(changes):
                comp.text = comp.text[:start] + comp.text[end:]
        # A reply that was only a change marker must not become an empty message.
        result.chain = [
            c for c in result.chain if not (isinstance(c, Plain) and not c.text.strip())
        ]
        parsed = [
            parse_markers(c.text) if isinstance(c, Plain) else [] for c in result.chain
        ]
        markers = [m for ms in parsed for m in ms]
        if not markers:
            return

        image_cfg = self.config.get("image_config") or {}
        photo_cfg = self.config.get("photo_config") or {}
        limit_cfg = self.config.get("limit_config") or {}
        budget = MAX_MARKERS_PER_REPLY
        if limit_cfg.get("enable_daily_limit", False):
            used = self.album.count_on(now.date())
            budget = min(budget, max(0, int(limit_cfg.get("daily_limit", 10)) - used))
        # Primary node first, then backups in order; incomplete nodes are skipped.
        nodes = [
            tuple(str(node.get(k, "") or "").strip() for k in NODE_KEYS)
            for node in [image_cfg, *(image_cfg.get("backup_providers") or [])]
            if isinstance(node, dict)
        ]
        nodes = [n for n in nodes if all(n)]
        if not nodes:
            budget = 0
        if budget and self._session is None:
            self._session = aiohttp.ClientSession()

        guard_cfg = self.config.get("guard_config") or {}
        prompts = resolve_prompts(self.config.get("prompt_config"))
        guard_words = [
            w
            for w in re.split(
                r"[,，、\s]+",
                str(guard_cfg.get("guard_keywords") or DEFAULT_GUARD_KEYWORDS),
            )
            if w
        ]

        async def run(marker) -> Path:
            if marker.kind != "doodle" and guard_cfg.get("enable_keyword_guard", False):
                hit = next((w for w in guard_words if w in marker.description), None)
                if hit:
                    raise RuntimeError(f"blocked by guard keyword {hit!r}")
            # Reference images in priority order: objects, then outfit and hand,
            # then the scene with whatever slots are left.
            max_refs = int(photo_cfg.get("max_reference_images", 4))
            refs: list[tuple[str, str, Path]] = []
            # With hands allowed, the image model may draw his hand whenever the
            # scene has him holding or touching something; the outfit and hand
            # references are only sent when the description clearly says so.
            show_hands = marker.kind != "doodle" and bool(
                photo_cfg.get("allow_hands", False)
            )
            outfit = self._current_outfit(now) if show_hands else ""
            if marker.kind != "doodle":
                for name in match_objects(self.dirs["objects"], marker.description):
                    refs.append(
                        ("object", name, first_image(self.dirs["objects"], name))
                    )
                if show_hands and any(w in marker.description for w in HAND_WORDS):
                    outfit_image = first_image(self.dirs["outfits"], outfit)
                    if outfit_image:
                        refs.append(("outfit", outfit, outfit_image))
                    hand_images = folder_images(self.dirs["hands"])
                    if hand_images:
                        refs.append(("hand", "", hand_images[0]))
                refs = refs[:max_refs]
                if marker.scene:
                    for path in pick_refs(
                        self.dirs["scenes"], marker.scene, now, max_refs - len(refs)
                    ):
                        refs.append(("scene", marker.scene, path))
            # Edits follow the reference images' aspect ratio, so crop the
            # references first; the final crop only trims a thin edge.
            ratio = str(
                photo_cfg.get(f"{marker.kind}_ratio", "") or DEFAULT_RATIOS[marker.kind]
            )
            # An unreadable reference is skipped instead of failing the photo;
            # labels are kept in step with the images actually sent.
            ref_images, labels = [], []
            for kind, name, path in refs:
                try:
                    data = prepare_reference(path.read_bytes(), ratio)
                except Exception as exc:
                    logger.warning(f"[glimpse] skip reference {path}: {exc!r}")
                    continue
                ref_images.append((f"{path.stem}.jpg", data))
                labels.append((kind, name))
            cinematic = photo_cfg.get("photo_style", "") == "氛围大片"
            prompt = build_prompt(
                marker,
                labels,
                now,
                cinematic,
                show_hands,
                self.config.get("prompt_config"),
                outfit,
            )
            # Each node gets its own timeout; the last error is raised if all fail.
            error: BaseException = RuntimeError("no image provider")
            for base_url, api_key, model in nodes:
                try:
                    image = await asyncio.wait_for(
                        generate_image(
                            self._session,
                            base_url,
                            api_key,
                            model,
                            prompt,
                            size_for_ratio(ratio),
                            ref_images,
                        ),
                        float(image_cfg.get("timeout_seconds", 90)),
                    )
                    break
                except Exception as exc:
                    logger.warning(f"[glimpse] {model} failed: {exc!r}")
                    error = exc
            else:
                raise error
            image = crop_to_ratio(image, ratio)
            # Optional last line of defence: a vision model looks for his face.
            # A failed check lets the photo through rather than swallowing it.
            if marker.kind != "doodle" and guard_cfg.get("enable_face_check", False):
                provider_id = str(guard_cfg.get("face_check_provider") or "")
                provider = (
                    self.context.get_provider_by_id(provider_id)
                    if provider_id
                    else self.context.get_using_provider(event.unified_msg_origin)
                )
                check_path = self.data_dir / f"face-check-{uuid.uuid4().hex[:8]}.png"
                try:
                    if provider is None:
                        raise RuntimeError("no vision provider available")
                    check_path.write_bytes(image)
                    response = await asyncio.wait_for(
                        provider.text_chat(
                            prompt=prompts["face_check_prompt"],
                            image_urls=[str(check_path)],
                        ),
                        30,
                    )
                    # Tolerate replies like "**YES**", "Yes." or "是".
                    answer = str(response.completion_text or "").strip(" *\"'“”`\n")
                    has_face = answer.upper().startswith("YES") or answer.startswith(
                        "是"
                    )
                except Exception as exc:
                    logger.warning(f"[glimpse] face check skipped: {exc!r}")
                    has_face = False
                finally:
                    check_path.unlink(missing_ok=True)
                if has_face:
                    raise RuntimeError("face detected in generated photo")
            return self.album.save(
                image,
                {
                    "kind": marker.kind,
                    "scene": marker.scene,
                    "description": marker.description,
                    "prompt": prompt,
                    "model": model,
                    "refs": [f"{k}:{p.name}" for k, _, p in refs],
                    "session": event.unified_msg_origin,
                },
            )

        outcomes = await asyncio.gather(
            *(run(m) for m in markers[:budget]), return_exceptions=True
        )
        paths = {}
        for marker, outcome in zip(markers, outcomes):
            if isinstance(outcome, BaseException):
                logger.warning(
                    f"[glimpse] {marker.kind} generation failed: {outcome!r}"
                )
            else:
                paths[id(marker)] = outcome

        # Rebuild the chain: fallback text merges into surrounding text so the
        # "$" segmentation still works; each image becomes its own component.
        new_chain = []
        for comp, comp_markers in zip(result.chain, parsed):
            if not comp_markers:
                new_chain.append(comp)
                continue
            buffer, cursor = "", 0
            for marker in comp_markers:
                buffer += comp.text[cursor : marker.start]
                cursor = marker.end
                path = paths.get(id(marker))
                if path is None:
                    buffer += fallback_text(marker)
                    continue
                if buffer:
                    new_chain.append(Plain(buffer))
                    buffer = ""
                new_chain.append(Image.fromFileSystem(str(path)))
            buffer += comp.text[cursor:]
            if buffer:
                new_chain.append(Plain(buffer))
        result.chain = new_chain

    async def terminate(self):
        """Close the shared HTTP session."""
        if self._session is not None:
            await self._session.close()
