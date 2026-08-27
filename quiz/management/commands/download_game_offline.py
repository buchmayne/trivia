"""
Download a single game's gallery content (questions, answers, rounds,
categories) plus all referenced media into a self-contained local bundle
(offline_bundle/) for playing gallery mode with no internet access.

This is a personal, dev-only tool. It is not used in production or CI.

Run this under normal settings (real Postgres DB, real internet access to
CloudFront) - not under pub_trivia.settings_offline:

    uv run manage.py download_game_offline "February-2026"

The argument is the game's title exactly as shown in gallery mode (falls back
to the numeric database id if no title match is found).

See docs/superpowers/specs/2026-08-15-offline-gallery-mode-design.md for the
full design.
"""

import copy
import shutil
from pathlib import Path

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, models

from quiz.models import Answer, Category, Game, Question, QuestionRound, QuestionType

OFFLINE_DB_ALIAS = "offline"

# The content models gallery mode needs, plus infrastructure tables required
# for a normal Django request/response cycle to run at all under the
# project's existing middleware stack (SessionMiddleware needs
# django_session; Game.owner is a nullable FK to User, and SQLite's
# foreign-key support requires the referenced table to exist even though we
# always clone Game with owner=None and never populate any User rows).
# Deliberately excludes GameSession/SessionTeam/TeamAnswer/GameResult/
# PlayerStats/etc - out of scope for offline gallery mode (see design spec).
OFFLINE_MODELS = [
    get_user_model(),
    Session,
    Category,
    QuestionType,
    QuestionRound,
    Game,
    Question,
    Answer,
]

# Media URL fields present on both Question and Answer.
MEDIA_URL_FIELDS = [
    "question_image_url",
    "answer_image_url",
    "question_video_url",
    "answer_video_url",
]


class Command(BaseCommand):
    help = (
        "Download a single game's gallery content and media into offline_bundle/ "
        "for offline play. Run under normal settings, not settings_offline."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "game",
            type=str,
            help=(
                "The game's title exactly as shown in gallery mode "
                "(e.g. 'February-2026'), or its numeric database id."
            ),
        )

    def handle(self, *args, **options):
        game = self._resolve_game(options["game"])

        bundle_dir = Path(settings.BASE_DIR) / "offline_bundle"
        media_dir = bundle_dir / "media"
        db_path = bundle_dir / "db.sqlite3"

        self.stdout.write(f"Rebuilding offline bundle for '{game}' at {bundle_dir}...")
        if bundle_dir.exists():
            shutil.rmtree(bundle_dir)
        media_dir.mkdir(parents=True)

        self._register_offline_database(db_path)
        self._create_offline_schema()

        questions = list(
            Question.objects.filter(game=game).select_related(
                "category", "question_type", "game_round"
            )
        )
        answers = list(Answer.objects.filter(question__in=questions))

        categories = {q.category for q in questions if q.category_id}
        categories.update(game.categories.all())
        question_types = {q.question_type for q in questions if q.question_type_id}
        rounds = {q.game_round for q in questions if q.game_round_id}

        # Copy rows in FK dependency order, preserving primary keys.
        offline_game = self._clone(game, owner=None)
        offline_categories = [self._clone(category) for category in categories]
        for question_type in question_types:
            self._clone(question_type)
        for game_round in rounds:
            self._clone(game_round)
        for question in questions:
            self._clone(question)
        for answer in answers:
            self._clone(answer)

        # Restore the game <-> category many-to-many links (offline-only,
        # ignoring any other games those categories may be linked to).
        if offline_categories:
            offline_game.categories.set(offline_categories)

        downloaded = 0
        failures = []
        for row in questions + answers:
            for field_name in MEDIA_URL_FIELDS:
                url = getattr(row, field_name, None)
                if not url:
                    continue
                ok = self._download_media(url, media_dir)
                if ok:
                    downloaded += 1
                else:
                    failures.append(url)

        bundle_size = sum(
            f.stat().st_size for f in bundle_dir.rglob("*") if f.is_file()
        )

        self.stdout.write(self.style.SUCCESS("\nOffline bundle ready."))
        self.stdout.write(f"  Game: {game}")
        self.stdout.write(f"  Questions: {len(questions)}")
        self.stdout.write(f"  Answers: {len(answers)}")
        self.stdout.write(f"  Media files downloaded: {downloaded}")
        self.stdout.write(f"  Bundle size: {bundle_size / (1024 * 1024):.1f} MB")
        if failures:
            self.stdout.write(
                self.style.WARNING(f"  Media download failures: {len(failures)}")
            )
            for url in failures:
                self.stdout.write(f"    - {url}")

    def _resolve_game(self, identifier: str) -> Game:
        """
        Resolve a Game from the same title shown in gallery mode
        (game_list.html displays `legacy_name|default:name`), falling back to
        a numeric database id for convenience.
        """
        matches = list(
            Game.objects.filter(
                models.Q(legacy_name=identifier) | models.Q(name=identifier)
            )
        )
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            ids = ", ".join(str(g.id) for g in matches)
            raise CommandError(
                f"Multiple games titled '{identifier}' found (ids: {ids}). "
                "Pass the numeric id instead."
            )

        if identifier.isdigit():
            try:
                return Game.objects.get(pk=int(identifier))
            except Game.DoesNotExist:
                pass

        raise CommandError(
            f"No game found titled '{identifier}' (checked gallery title and id). "
            "Copy the title exactly as shown in gallery mode."
        )

    def _register_offline_database(self, db_path: Path) -> None:
        """
        Register a temporary database alias pointed at the offline SQLite
        file. settings.DATABASES was already normalized with defaults by
        Django's ConnectionHandler at startup, so a newly added alias needs
        those same defaults applied manually (they're only auto-applied to
        entries present at process start).
        """
        settings.DATABASES[OFFLINE_DB_ALIAS] = {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(db_path),
            "ATOMIC_REQUESTS": False,
            "AUTOCOMMIT": True,
            "CONN_MAX_AGE": 0,
            "CONN_HEALTH_CHECKS": False,
            "OPTIONS": {},
            "TIME_ZONE": None,
            "USER": "",
            "PASSWORD": "",
            "HOST": "",
            "PORT": "",
            "TEST": {
                "CHARSET": None,
                "COLLATION": None,
                "MIGRATE": True,
                "MIRROR": None,
                "NAME": None,
            },
        }

    def _create_offline_schema(self) -> None:
        """
        Create tables for OFFLINE_MODELS directly from their current model
        definitions, without replaying migration history.

        This deliberately avoids `manage.py migrate` here. Several historical
        data migrations in this app (e.g. 0042_add_is_example_game,
        0049_migrate_game_naming_data) query models without explicitly
        scoping to the migration's target database. Replaying them from
        scratch against a fresh offline database causes that kind of
        unscoped query to silently fall back to the "default" alias -
        mutating the real database instead of the disposable offline one
        (this happened once during development of this command and required
        restoring the real database from a backup). Since we don't need any
        of that historical data-migration behavior anyway - this command
        populates offline content itself via _clone() - building the schema
        directly from current models sidesteps the entire bug class rather
        than working around individual instances of it.
        """
        connection = connections[OFFLINE_DB_ALIAS]
        with connection.schema_editor() as schema_editor:
            for model in OFFLINE_MODELS:
                schema_editor.create_model(model)

    def _clone(self, instance, **overrides):
        """
        Copy a model instance (read from the default database) into the
        offline database, preserving its primary key so foreign keys among
        copied rows continue to resolve correctly.
        """
        clone = copy.copy(instance)
        clone._state.adding = True
        clone._state.db = OFFLINE_DB_ALIAS
        for field_name, value in overrides.items():
            setattr(clone, field_name, value)
        clone.save(using=OFFLINE_DB_ALIAS, force_insert=True)
        return clone

    def _download_media(self, url: str, media_dir: Path) -> bool:
        """
        Download a single media file (given its full CloudFront URL) into
        media_dir, preserving the relative path so CloudFrontURLField can
        resolve it unchanged under settings_offline. Returns True on success.
        """
        relative_path = url.replace(settings.AWS_CLOUDFRONT_DOMAIN, "").lstrip("/")
        if not relative_path:
            return False

        dest_path = media_dir / relative_path
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            self.stderr.write(self.style.WARNING(f"Failed to download {url}: {exc}"))
            return False

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(response.content)
        return True
