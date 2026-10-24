"""
Image optimization for S3 uploads.

Trivia screenshots are taken on macOS and arrive as PNG (1-5 MB each). This
module converts every uploaded image to WebP (quality IMAGE_WEBP_QUALITY,
default 80) and downscales it to at most IMAGE_MAX_DIMENSION_PX (default 1920)
on the long edge, which is the ceiling any venue projector needs. The result
is typically 10x smaller with no visible difference at display resolution.

Pass-through rules (the original bytes are returned unchanged):
- Animated images (converting would flatten them to a static frame).
- Files Pillow cannot identify or decode.

A processing failure must never block a save and must never corrupt a file,
so every error path returns the original bytes and logs a warning.
"""

import logging
from io import BytesIO
from pathlib import PurePosixPath

from django.conf import settings
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)


def optimize_image(data: bytes, filename: str) -> tuple[bytes, str]:
    """Convert image ``data`` to WebP, downscale to the max long edge.

    Returns ``(bytes, filename)``. On success the filename has its extension
    replaced with ``.webp`` (parents in the path are preserved). On a
    pass-through case (animated or undecodable input) the original arguments
    are returned unchanged, so callers can detect "no conversion" by comparing
    bytes.
    """
    max_dim = int(getattr(settings, "IMAGE_MAX_DIMENSION_PX", 1920))
    quality = int(getattr(settings, "IMAGE_WEBP_QUALITY", 80))

    try:
        img = Image.open(BytesIO(data))
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        logger.warning(
            "Could not process %s (%s); uploading the original unchanged",
            filename,
            exc,
        )
        return data, filename

    try:
        with img:
            if getattr(img, "is_animated", False):
                logger.warning(
                    "%s is animated; uploading the original unchanged", filename
                )
                return data, filename

            # Normalize the color mode for WebP: keep alpha where present,
            # otherwise move to RGB.
            has_alpha = img.mode in ("RGBA", "LA", "PA") or (
                img.mode == "P" and "transparency" in img.info
            )
            img = img.convert("RGBA" if has_alpha else "RGB")

            if max(img.size) > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

            buf = BytesIO()
            img.save(buf, format="WEBP", quality=quality, method=6)
            new_bytes = buf.getvalue()
    except (OSError, ValueError) as exc:
        logger.warning(
            "Conversion failed for %s (%s); uploading the original unchanged",
            filename,
            exc,
        )
        return data, filename

    return new_bytes, str(PurePosixPath(filename).with_suffix(".webp"))
