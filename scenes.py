"""Reference libraries: one sub-folder per scene, object or outfit."""

from datetime import datetime, timedelta
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
TIME_TAGS = ("白天", "夜晚")
SCHEDULED_CATEGORIES = ("制服", "便服", "睡衣")


def folder_images(folder: Path) -> list[Path]:
    """List the images directly inside a folder, sorted by name.

    Args:
        folder: Directory to scan.

    Returns:
        Image paths; empty if the folder does not exist.
    """
    if not folder.is_dir():
        return []
    return sorted(
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )


def list_scenes(root: Path) -> list[str]:
    """List scene names (sub-folders that contain at least one image).

    Args:
        root: Scene library directory.

    Returns:
        Sorted scene names; empty if the directory does not exist.
    """
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if folder_images(p))


def pick_refs(root: Path, scene: str, now: datetime, max_refs: int) -> list[Path]:
    """Pick reference images of a scene for the current time of day.

    Images whose name contains "白天"/"夜晚" are used only in the matching period
    (daytime is 6:00-18:00) and come first; untagged images are always used. If
    nothing is left, every image of the scene is used.

    Args:
        root: Scene library directory.
        scene: Scene folder name.
        now: Current local time.
        max_refs: Maximum number of images to return.

    Returns:
        Reference image paths; empty for unknown scenes.
    """
    # The scene name comes from the model: only accept known folder names so it
    # can never be used as a path outside the scene library.
    images = folder_images(root / scene) if scene in list_scenes(root) else []
    tag = "白天" if 6 <= now.hour < 18 else "夜晚"
    matching = [p for p in images if tag in p.stem]
    untagged = [p for p in images if not any(t in p.stem for t in TIME_TAGS)]
    return (matching + untagged or images)[:max_refs]


def first_image(root: Path, name: str) -> Path | None:
    """Return the first image of a library folder.

    Args:
        root: Library directory.
        name: Folder name.

    Returns:
        The first image path, or None if the folder is unknown or empty.
    """
    images = folder_images(root / name) if name in list_scenes(root) else []
    return images[0] if images else None


def match_objects(root: Path, description: str) -> list[str]:
    """Find object folders whose names appear in a description.

    Args:
        root: Object library directory.
        description: Xavier's description of the photo.

    Returns:
        Matched names, in order of first appearance in the description.
    """
    found = [name for name in list_scenes(root) if name in description]
    return sorted(found, key=description.index)


def pick_outfit(
    root: Path, now: datetime, work_hours: tuple[int, int], sleep_hours: tuple[int, int]
) -> str:
    """Pick today's outfit folder for the current time.

    Folders are named "类别-名称" with 类别 in 制服/便服/睡衣. Weekdays within
    work_hours use 制服, the sleep window (which may cross midnight) uses 睡衣,
    other times use 便服. Within a category the choice is fixed per day, where
    a day starts at the end of the sleep window (his wake-up time).

    Args:
        root: Outfit library directory.
        now: Current local time.
        work_hours: (start, end) hours of the work day, end exclusive.
        sleep_hours: (start, end) hours of the sleep window, end exclusive.

    Returns:
        The outfit folder name, or "" if there are no outfits.
    """
    outfits = list_scenes(root)
    category = outfit_category(now, work_hours, sleep_hours)
    # Occasion outfits (any other prefix) are never worn automatically unless
    # they are all he has.
    candidates = (
        [o for o in outfits if o.split("-", 1)[0] == category]
        or [o for o in outfits if o.split("-", 1)[0] in SCHEDULED_CATEGORIES]
        or outfits
    )
    if not candidates:
        return ""
    # His "day" starts when he wakes up, so a late-night chat keeps the same set.
    day = (now - timedelta(hours=sleep_hours[1])).date()
    return candidates[day.toordinal() % len(candidates)]


def outfit_category(
    now: datetime, work_hours: tuple[int, int], sleep_hours: tuple[int, int]
) -> str:
    """Return the outfit category the schedule calls for at a given time.

    Args:
        now: Local time.
        work_hours: (start, end) hours of the work day, end exclusive.
        sleep_hours: (start, end) hours of the sleep window, may cross midnight.

    Returns:
        "睡衣", "制服" or "便服".
    """
    start, end = sleep_hours
    asleep = (
        start <= now.hour or now.hour < end if start > end else start <= now.hour < end
    )
    if asleep:
        return "睡衣"
    if now.weekday() < 5 and work_hours[0] <= now.hour < work_hours[1]:
        return "制服"
    return "便服"


def wardrobe(
    root: Path, now: datetime, work_hours: tuple[int, int], sleep_hours: tuple[int, int]
) -> list[str]:
    """List the outfits he may change into right now.

    That is the outfits of the category the schedule calls for, plus every
    occasion outfit (a prefix other than 制服/便服/睡衣, e.g. 正装 or 泳装).

    Args:
        root: Outfit library directory.
        now: Local time.
        work_hours: (start, end) hours of the work day.
        sleep_hours: (start, end) hours of the sleep window.

    Returns:
        Outfit folder names.
    """
    outfits = list_scenes(root)
    category = outfit_category(now, work_hours, sleep_hours)
    return [
        o
        for o in outfits
        if o.split("-", 1)[0] == category
        or o.split("-", 1)[0] not in SCHEDULED_CATEGORIES
    ]


def next_category_change(
    now: datetime, work_hours: tuple[int, int], sleep_hours: tuple[int, int]
) -> datetime:
    """Return the next full hour at which the scheduled outfit category changes.

    Args:
        now: Local time.
        work_hours: (start, end) hours of the work day.
        sleep_hours: (start, end) hours of the sleep window.

    Returns:
        The time of the next category change, at most 48 hours ahead.
    """
    current = outfit_category(now, work_hours, sleep_hours)
    t = now.replace(minute=0, second=0, microsecond=0)
    for _ in range(48):
        t += timedelta(hours=1)
        if outfit_category(t, work_hours, sleep_hours) != current:
            return t
    return t
