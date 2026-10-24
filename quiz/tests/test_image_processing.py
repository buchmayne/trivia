from io import BytesIO

from django.test import TestCase
from PIL import Image

from quiz.image_processing import optimize_image


def _image_bytes(fmt, size=(100, 80), mode="RGB", **save_kwargs):
    """Build an in-memory image in the given format for tests."""
    img = Image.new(mode, size)
    buf = BytesIO()
    img.save(buf, format=fmt, **save_kwargs)
    return buf.getvalue()


class OptimizeImageConversionTest(TestCase):
    """optimize_image: active conversions"""

    def test_png_converted_to_webp(self):
        data = _image_bytes("PNG")
        new_bytes, new_name = optimize_image(data, "screenshot.png")

        self.assertEqual(new_name, "screenshot.webp")
        img = Image.open(BytesIO(new_bytes))
        self.assertEqual(img.format, "WEBP")

    def test_jpeg_converted_to_webp(self):
        data = _image_bytes("JPEG")
        new_bytes, new_name = optimize_image(data, "photo.jpg")

        self.assertEqual(new_name, "photo.webp")
        img = Image.open(BytesIO(new_bytes))
        self.assertEqual(img.format, "WEBP")

    def test_small_image_not_upscaled(self):
        data = _image_bytes("PNG", size=(500, 400))
        new_bytes, _ = optimize_image(data, "small.png")

        img = Image.open(BytesIO(new_bytes))
        self.assertEqual(img.size, (500, 400))

    def test_large_image_downscaled_to_max_long_edge(self):
        data = _image_bytes("PNG", size=(3000, 2000))
        new_bytes, _ = optimize_image(data, "big.png")

        img = Image.open(BytesIO(new_bytes))
        self.assertEqual(img.size, (1920, 1280))

    def test_alpha_preserved(self):
        # Fully transparent RGBA PNG
        img = Image.new("RGBA", (100, 80), (255, 0, 0, 0))
        buf = BytesIO()
        img.save(buf, format="PNG")
        new_bytes, _ = optimize_image(buf.getvalue(), "alpha.png")

        out = Image.open(BytesIO(new_bytes))
        self.assertEqual(out.mode, "RGBA")
        self.assertEqual(out.getpixel((0, 0))[3], 0)

    def test_directory_in_filename_preserved(self):
        data = _image_bytes("PNG")
        _, new_name = optimize_image(data, "game-1/Cat/screenshot.png")

        self.assertEqual(new_name, "game-1/Cat/screenshot.webp")


class OptimizeImagePassThroughTest(TestCase):
    """optimize_image: cases that must return the original unchanged."""

    def test_animated_gif_passes_through_unchanged(self):
        frames = [
            Image.new("P", (50, 50), color) for color in ((255, 0, 0), (0, 255, 0))
        ]
        buf = BytesIO()
        frames[0].save(
            buf, format="GIF", save_all=True, append_images=frames[1:], loop=0
        )

        original = buf.getvalue()
        result = optimize_image(original, "anim.gif")

        self.assertEqual(result, (original, "anim.gif"))

    def test_corrupt_file_passes_through_unchanged(self):
        data = b"this is definitely not an image"
        result = optimize_image(data, "broken.png")

        self.assertEqual(result, (data, "broken.png"))
