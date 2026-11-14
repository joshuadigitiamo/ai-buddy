"""Upload the Guides videos named in the README table to the private bucket (D-16, D-17).

The README table is the only source of which videos exist. Each file is found by name under the
given local directories, compared with the object by content hash (md5, as the bucket reports it)
and uploaded only when absent or different. Every README video must have a local file: the run
fails listing the missing names, so no index can point at an object that was never uploaded.
Output and errors carry counts and file names only, never paths or credentials.
"""

import base64
import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from buddy_core.store import BucketPort
from buddy_sync.video_map import VIDEO_OBJECT_DIR, VideoMapError, VideoPart, video_names

CONTENT_TYPE: Final = "video/mp4"
CONTENT_DISPOSITION: Final = "inline"
CACHE_CONTROL: Final = "private"
_HASH_CHUNK: Final = 1 << 20


class VideoUploadError(Exception):
    """The README names a video that cannot be uploaded safely."""


@dataclass(frozen=True, slots=True)
class UploadReport:
    """Counts of one upload run."""

    uploaded: int
    unchanged: int


def _md5_base64(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK):
            digest.update(chunk)
    return base64.b64encode(digest.digest()).decode("ascii")


def _find_local_files(wanted: set[str], video_dirs: Sequence[Path]) -> dict[str, Path]:
    """One local file per wanted name; the same name with different bytes is refused."""
    found: dict[str, Path] = {}
    digests: dict[str, str] = {}
    for directory in video_dirs:
        for path in sorted(directory.rglob("*.mp4")):
            if path.name not in wanted or not path.is_file():
                continue
            digest = _md5_base64(path)
            if found.setdefault(path.name, path) is path:
                digests[path.name] = digest
            elif digests[path.name] != digest:
                raise VideoUploadError(
                    f"video {path.name!r} exists with different content in two places"
                )
    return found


def upload_videos(
    readme_videos: Mapping[str, Sequence[VideoPart]],
    video_dirs: Sequence[Path],
    bucket: BucketPort,
) -> UploadReport:
    """Upload every README video to ``videos/<name>.mp4`` unless the bucket already holds it."""
    try:
        names = video_names(readme_videos)
    except VideoMapError as exc:
        raise VideoUploadError(str(exc)) from exc
    found = _find_local_files(set(names), video_dirs)

    uploaded = 0
    unchanged = 0
    for name in names:
        path = found.get(name)
        if path is None:
            continue
        object_name = f"{VIDEO_OBJECT_DIR}/{name}"
        if bucket.md5_base64(object_name) == _md5_base64(path):
            unchanged += 1
            continue
        bucket.upload_file(
            path,
            object_name,
            content_type=CONTENT_TYPE,
            content_disposition=CONTENT_DISPOSITION,
            cache_control=CACHE_CONTROL,
        )
        uploaded += 1

    missing = [name for name in names if name not in found]
    if missing:
        raise VideoUploadError(
            f"{len(missing)} README video file(s) not found locally: {', '.join(missing)}"
        )
    return UploadReport(uploaded=uploaded, unchanged=unchanged)
