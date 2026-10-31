"""Parse camera / film / doodle markers out of Xavier's replies."""

import re
from dataclasses import dataclass

MARKER_RE = re.compile(
    r"\[\s*(?:📷|🎞️|🎞|✏️|✏)?\s*(拍照|照片|胶片|涂鸦)\s*"
    r"(?:[·・\-—]\s*([^:：\]]+?)\s*)?[:：]\s*([^\]]+?)\s*\]"
)
KIND_BY_WORD = {"拍照": "photo", "照片": "photo", "胶片": "film", "涂鸦": "doodle"}
OUTFIT_RE = re.compile(r"\[\s*(?:👕)?\s*换装\s*[:：]\s*([^\]]+?)\s*\]")
SCENE_SEPARATORS = re.compile(r"\s*[·・—–－]+\s*")


def parse_outfit_changes(text: str) -> list[tuple[int, int, str]]:
    """Find invisible outfit-change markers such as `[👕换装：便服-白衬衫]`.

    Args:
        text: Reply text.

    Returns:
        (start, end, outfit name) for each marker, in order.
    """
    return [(m.start(), m.end(), m.group(1)) for m in OUTFIT_RE.finditer(text)]


@dataclass(frozen=True)
class Marker:
    """A marker found in a reply.

    Attributes:
        kind: One of "photo", "film" or "doodle".
        scene: Scene folder name, or "" for free scenes (always "" for doodles).
        description: Xavier's natural-language description.
        start: Start offset of the marker in the source text.
        end: End offset (exclusive) of the marker in the source text.
    """

    kind: str
    scene: str
    description: str
    start: int
    end: int


def parse_markers(text: str) -> list[Marker]:
    """Find all image markers in text, in order of appearance.

    Args:
        text: Reply text that may contain markers.

    Returns:
        Markers in order. The plain `[📷分享图片：…]` form is not a marker.
    """
    markers = []
    for match in MARKER_RE.finditer(text):
        kind = KIND_BY_WORD[match.group(1)]
        scene = (match.group(2) or "").strip() if kind != "doodle" else ""
        scene = SCENE_SEPARATORS.sub("-", scene).strip("-")
        markers.append(
            Marker(kind, scene, match.group(3).strip(), match.start(), match.end())
        )
    return markers


def fallback_text(marker: Marker) -> str:
    """Return the text shown instead of an image when generation is skipped.

    Args:
        marker: The marker that could not be rendered.

    Returns:
        A text-only marker that reads naturally in chat.
    """
    if marker.kind == "doodle":
        return f"[✏️涂鸦：{marker.description}]"
    return f"[📷分享图片：{marker.description}]"
