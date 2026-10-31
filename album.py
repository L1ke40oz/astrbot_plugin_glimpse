"""Album: generated images plus a JSON Lines metadata log."""

import json
import uuid
from datetime import date, datetime
from pathlib import Path


class Album:
    """Stores generated images under one directory with album.jsonl metadata."""

    def __init__(self, root: Path):
        """Create the album directory if needed.

        Args:
            root: Directory holding images and album.jsonl.
        """
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.meta_path = root / "album.jsonl"

    def save(self, image: bytes, meta: dict) -> Path:
        """Save an image and append its metadata line.

        Args:
            image: Image bytes.
            meta: Metadata (kind, scene, description, prompt, refs, session).

        Returns:
            Path of the saved image.
        """
        now = datetime.now()
        path = self.root / f"{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}.png"
        path.write_bytes(image)
        record = {
            **meta,
            "file": path.name,
            "created_at": now.isoformat(timespec="seconds"),
        }
        with self.meta_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return path

    def count_on(self, day: date) -> int:
        """Count images created on a given day.

        Args:
            day: The local date to count.

        Returns:
            Number of records whose created_at falls on that day.
        """
        if not self.meta_path.exists():
            return 0
        count = 0
        prefix = day.isoformat()
        for line in self.meta_path.read_text(encoding="utf-8").splitlines():
            try:
                if json.loads(line).get("created_at", "").startswith(prefix):
                    count += 1
            except (ValueError, AttributeError):
                continue
        return count
