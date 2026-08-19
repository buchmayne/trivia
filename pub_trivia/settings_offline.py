"""
Offline settings for running a single downloaded game in gallery mode with no
internet access (e.g. hosting trivia while camping).

This is a personal, dev-only tool. It is never used in production or CI. Do not
import this module from settings.py or reference it anywhere in the normal
request path - it must only be activated explicitly via
DJANGO_SETTINGS_MODULE=pub_trivia.settings_offline.

Usage:
    uv run manage.py download_game_offline <game_id>   # while online, populates offline_bundle/
    DJANGO_SETTINGS_MODULE=pub_trivia.settings_offline uv run manage.py runserver

See docs/superpowers/specs/2026-08-15-offline-gallery-mode-design.md for the full design.
"""

from .settings import *  # noqa: F401,F403

OFFLINE_MODE = True

OFFLINE_BUNDLE_DIR = BASE_DIR / "offline_bundle"  # noqa: F405

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": OFFLINE_BUNDLE_DIR / "db.sqlite3",
    }
}

MEDIA_ROOT = OFFLINE_BUNDLE_DIR / "media"

# CloudFrontURLField prefixes this domain onto stored relative paths. Pointing it
# at the local media URL means image/video tags resolve to files served locally
# from MEDIA_ROOT instead of CloudFront.
AWS_CLOUDFRONT_DOMAIN = "/media"
AWS_S3_CUSTOM_DOMAIN = AWS_CLOUDFRONT_DOMAIN
