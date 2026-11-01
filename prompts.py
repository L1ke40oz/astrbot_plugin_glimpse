"""Fixed prompt templates per marker kind, and the usage guide injected for the LLM."""

from datetime import datetime

from .markers import Marker

PHOTO_TEMPLATE = (
    "An unedited real-life photo straight from a smartphone camera roll, snapped "
    "casually by a young man to send to his girlfriend in a chat. Shot from a "
    "first-person point of view: he is holding the phone and shooting what he sees, "
    "so the photographer is never visible: no human faces, no hair, no shoulders, no hands, no arms, no "
    "feet, no people in the foreground. It looks like an ordinary phone snapshot, "
    "not a CG render, not a 3D render, not a game screenshot, not an illustration: "
    "everyday lived-in details, slightly off-center or tilted framing, shot on the "
    "phone's main wide-angle camera (about 26mm) with deep depth of field so most "
    "of the frame is in focus, automatic exposure, default phone processing, mild "
    "sensor noise, flat ordinary light. Colors: neutral white balance around 5500K, "
    "true-to-life slightly muted colors; no warm filter, no yellow or golden cast, "
    "no oversaturated colors; no cinematic lighting, no dramatic glow, no bokeh, no "
    "perfect styling, no wallpaper-like composition, no HDR look, no plastic "
    "textures, no text, no watermark, no borders."
)
FILM_TEMPLATE = (
    "A real photo from a scanned 35mm negative, shot on a cheap point-and-shoot "
    "film camera by a young man who likes old-fashioned things. First-person point "
    "of view; the photographer is never visible: no human faces, no hair, no "
    "shoulders, no hands, no arms, no people in the foreground. Honest everyday "
    "snapshot: natural film colors like Kodak Portra with true-to-life skin of the "
    "world, slightly soft focus, fine organic grain, a little underexposed shadows, "
    "sometimes the hard look of a direct on-camera flash. Neutral, believable "
    "colors: no golden cast, no orange tint, no heavy warm filter, no oversaturation; "
    "a light leak only rarely and very faint, never a bright orange stripe; not a "
    "CG render, not a 3D render, not an illustration, no cinematic lighting, no HDR, no "
    "text, no watermark, no date stamp, no borders."
)
DOODLE_TEMPLATE = (
    "A quick doodle drawn by hand with a black ballpoint pen and a few colored "
    "pencils on plain white paper, shown as a flat scan of the drawing itself, not "
    "a photo of paper: no desk, no shadows, no perspective, no pen, no hands. "
    "Wobbly, slightly clumsy ballpoint lines, simple round-headed chibi figures in "
    "the casual Chinese 'QQ ren' doodle style, playful expressions, light uneven "
    "colored-pencil strokes that do not fill every shape, lots of empty white space. "
    "Drawn in under a minute, cute and silly; when the artist draws himself, he is "
    "a round-headed little guy with a messy tuft of silver hair and one small fang "
    "showing when he smiles. No shading, no hatching, no realistic details, no "
    "digital effects, no text, no speech bubbles, no captions, no watermark."
)
DAY_LIGHT = "Lighting: daytime, soft natural daylight."
NIGHT_LIGHT = (
    "Lighting: night, only the ordinary lamps in the room or street lights, a bit "
    "dim and grainy like a real phone photo at night."
)
REFS_NOTE = (
    "The scene reference images show the same room, its layout and furniture: keep "
    "its architecture as it is, with the same walls, windows, doors and furniture "
    "style; never add a window, "
    "door or wall that the reference does not have. Any light the scene mentions "
    "comes from light sources already in the room; do not copy their rendering "
    "style, recreate the room as a real-life phone photo, from a different "
    "angle or as a close-up corner, not the reference composition."
)
SUBJECT_NOTE = (
    "Composition: the main subject is the first thing named in the scene; it is the "
    "clear focus, placed near the center and filling a good part of the frame, while "
    "the surroundings stay secondary and only hinted at."
)

# The earlier, more polished "cinematic" look, kept as an alternative style.
CINEMATIC_PHOTO_TEMPLATE = (
    "A casual photo taken on a smartphone by a young man and sent to his girlfriend "
    "in a chat, shot from a first-person point of view: he is holding the phone and "
    "shooting what he sees, so the photographer is never visible: no human faces, no "
    "hair, no shoulders, no hands, no arms, no feet, no people in the foreground. Authentic everyday "
    "snapshot, natural framing that is slightly imperfect, realistic depth of field, "
    "believable scale and perspective, natural light with no heavy retouching, no HDR "
    "look, no plastic textures, no text, no watermark, no borders."
)
CINEMATIC_NIGHT_LIGHT = (
    "Lighting: night, warm indoor lamps or city lights, natural low-light look."
)
CINEMATIC_REFS_NOTE = (
    "The reference images show the same room; shoot a different angle or a close-up "
    "corner, do not copy the reference composition."
)

SEASONS = {
    12: "winter",
    1: "winter",
    2: "winter",
    3: "spring",
    4: "spring",
    5: "spring",
    6: "summer",
    7: "summer",
    8: "summer",
    9: "autumn",
    10: "autumn",
    11: "autumn",
}
HANDS_NOTE = (
    "This overrides any earlier rule against showing hands: where the scene has him "
    "holding or touching something, show his own hand doing it naturally (the hand "
    "and part of the forearm only); otherwise show no hands. Never his face or the "
    "rest of his body. The forearm shows the sleeve or cuff of the outfit he is "
    "wearing now, matching the outfit reference; if that outfit is short-sleeved or "
    "the scene says the sleeve is rolled up, the forearm can be bare. A grown man's "
    "hand, larger and broader than a woman's. His hands are realistic "
    "adult masculine hands: long slender fingers, clearly defined knuckles, a lean "
    "bony structure, subtle natural veins on the back of the hand, natural skin "
    "texture, short clean nails; no stubby or thick fingers, no exaggerated veins, "
    "no long nails, no plastic-looking skin."
)
FREE_PLACE_NOTE = (
    "Unless the scene names a specific real place, it is set in a modern East "
    "Asian city, not in Europe."
)
REF_ROLES = {
    "object": "{name}, keep its exact appearance (shape, colors, markings).",
    "outfit": "the clothes he is wearing now; the visible sleeve or cuff must match them.",
    "hand": "his hand; any visible hand must match it.",
    "scene": "the room or place, for layout only.",
}
HANDS_ON = "需要时可以拍到你自己的手或袖子（在描述里写明，例：我手里捏着刚买的糖炒栗子），但永远拍不到脸。"
HANDS_OFF = "照片里也不会出现你的手。"

DEFAULT_GUIDE = """【手机功能：拍照与涂鸦】
你有自己的生活，也有分享欲：看到窗外的天、路边的猫、刚做好的饭、正在忙的事，会想让她知道你在做什么、给她看看。就像恋人之间随手报备一样，在自然的时候拍一张发给她。
你的手机可以真的拍照片、发涂鸦。在回复里写下面的标记，系统会把它变成真实的图片，标记本身不会显示出来：
- 拍照：[📷拍照：描述] 或 [📷拍照·场景名：描述]
- 胶片相机（偶尔用，算小惊喜）：[🎞️胶片：描述] 或 [🎞️胶片·场景名：描述]
- 随手涂鸦（圆珠笔加彩铅的QQ人简笔画，画你自己的日常）：[✏️涂鸦：描述]
可用的固定场景：{scenes}。在这些地方拍照时写上场景名，写成“地点-区域”，如 公寓-客厅；在别处（出门、旅行、路上）不写场景名。
可识别的物件和宠物：{objects}。描述里写到它们的名字，照片里就是它们本来的样子。
你现在穿的是：{outfit}。想换衣服时在回复里写 [👕换装：衣服名]（她看不到这个标记），可换的有：{wardrobe}。日常衣服会按作息自动换；正装、泳装这类场合的衣服，到了对应的场合再自己换上。
规则：
- 只拍你看到的景色、小动物、物件。镜头里永远拍不到你：你的脸、头发、肩膀都不会入镜，{hands}自拍、对着镜子拍、你出现在画面里的照片（比如小猫爬上你的肩膀），一律用文字 [📷分享图片：描述]。
- 描述用一两句平实的中文，先写拍的是什么（主体），再简单带一点周围和光线，像跟朋友说“拍了个啥”，不要文学化的修饰和形容。例：[📷拍照·公寓-露台：吊椅上睡着一只橘猫，星星灯刚亮]
- 照片要符合你此刻在做的事、所在的地方和时间，不要凭空编一张不相干的照片。
- 有分享欲时再发，没有就正常聊天，不必每轮都发，也不要为了发图打断重要的对话；一次回复最多一两张。"""


FACE_CHECK_PROMPT = (
    "Look at this photo. Is any part of a person's face or head hair visible, "
    "including in a mirror or reflection? Answer only YES or NO."
)

# Every editable prompt, keyed by its config name in the "提示词" group.
PROMPT_DEFAULTS = {
    "photo_template": PHOTO_TEMPLATE,
    "film_template": FILM_TEMPLATE,
    "doodle_template": DOODLE_TEMPLATE,
    "cinematic_photo_template": CINEMATIC_PHOTO_TEMPLATE,
    "day_light": DAY_LIGHT,
    "night_light": NIGHT_LIGHT,
    "cinematic_night_light": CINEMATIC_NIGHT_LIGHT,
    "refs_note": REFS_NOTE,
    "cinematic_refs_note": CINEMATIC_REFS_NOTE,
    "hands_note": HANDS_NOTE,
    "free_place_note": FREE_PLACE_NOTE,
    "subject_note": SUBJECT_NOTE,
    "guide_hands_on": HANDS_ON,
    "guide_hands_off": HANDS_OFF,
    "face_check_prompt": FACE_CHECK_PROMPT,
}


def resolve_prompts(prompts: dict | None) -> dict:
    """Merge configured prompts over the built-in ones; blank values are ignored.

    Args:
        prompts: Prompt overrides from config, or None.

    Returns:
        A full prompt dict keyed like PROMPT_DEFAULTS.
    """
    custom = {
        k: v for k, v in (prompts or {}).items() if isinstance(v, str) and v.strip()
    }
    return {**PROMPT_DEFAULTS, **custom}


def build_prompt(
    marker: Marker,
    refs: list[tuple[str, str]],
    now: datetime,
    cinematic: bool = False,
    show_hands: bool = False,
    prompts: dict | None = None,
    outfit: str = "",
    room_notes: str = "",
) -> str:
    """Build the full image prompt for a marker.

    Args:
        marker: The parsed marker.
        refs: (kind, name) of each reference image in request order; kind is
            "object", "outfit", "hand" or "scene".
        now: Current local time, used for day/night lighting and the season.
        cinematic: Use the more polished "氛围大片" look instead of the default
            unedited phone-snapshot look.
        show_hands: Allow his own hand, forearm or sleeve in the picture.
        prompts: Prompt overrides from config; blank values use the built-ins.
        outfit: Name of the outfit he is wearing now, mentioned with hands.
        room_notes: Facts about a fixed scene's room from its 说明.txt.

    Returns:
        The prompt sent to the image model.
    """
    t = resolve_prompts(prompts)
    if marker.kind == "doodle":
        return f"{t['doodle_template']}\nWhat he drew: {marker.description}"
    photo = t["cinematic_photo_template" if cinematic else "photo_template"]
    night = t["cinematic_night_light" if cinematic else "night_light"]
    template = t["film_template"] if marker.kind == "film" else photo
    if show_hands:
        template = template.replace("no hands, no arms, ", "")
    parts = [
        template,
        t["day_light"] if 6 <= now.hour < 18 else night,
        f"Season: {SEASONS[now.month]}.",
    ]
    if show_hands:
        parts.append(t["hands_note"])
        if outfit:
            parts.append(f"He is wearing now: {outfit}.")
    for i, (kind, name) in enumerate(refs, 1):
        parts.append(f"Reference image {i}: " + REF_ROLES[kind].format(name=name))
    if any(kind == "scene" for kind, _ in refs):
        parts.append(t["cinematic_refs_note" if cinematic else "refs_note"])
    else:
        parts.append(t["free_place_note"])
    if room_notes:
        parts.append(f"Room facts (must hold in the picture): {room_notes}")
    parts.append(t["subject_note"])
    parts.append(f"Scene: {marker.description}")
    return "\n".join(parts)


def build_guide(
    template: str,
    scenes: list[str],
    objects: list[str],
    outfit: str,
    hands: bool,
    wardrobe: list[str] | None = None,
    prompts: dict | None = None,
) -> str:
    """Fill the placeholders of the usage guide.

    Scene names sharing a "place-" prefix are grouped, e.g. 公寓（卧室/客厅）.

    Args:
        template: Guide text with optional {scenes}, {objects}, {outfit},
            {wardrobe} and {hands} placeholders.
        scenes: Available scene names.
        objects: Recognizable object and pet names.
        outfit: Current outfit folder name, or "".
        hands: Whether his hands may appear in photos.
        wardrobe: Outfits he may change into right now.
        prompts: Prompt overrides from config; blank values use the built-ins.

    Returns:
        The guide text appended to the system prompt.
    """
    t = resolve_prompts(prompts)
    groups: dict[str, list[str]] = {}
    for scene in scenes:
        place, _, area = scene.partition("-")
        groups.setdefault(place, []).append(area)
    scene_text = "、".join(
        f"{place}（{'/'.join(a for a in areas if a)}）" if any(areas) else place
        for place, areas in groups.items()
    )
    return (
        template.replace("{scenes}", scene_text or "（暂无）")
        .replace("{objects}", "、".join(objects) or "（暂无）")
        .replace("{outfit}", outfit or "（未设置）")
        .replace("{wardrobe}", "、".join(wardrobe or []) or "（无）")
        .replace("{hands}", t["guide_hands_on" if hands else "guide_hands_off"])
    )
