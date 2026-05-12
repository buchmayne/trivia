import json
import tempfile
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


# Models to exclude from fixture loading
# These are either system models, user data (preserved in production),
# session data (ephemeral), or analytics data (imported separately)
EXCLUDED_MODELS = {
    # System
    "contenttypes.contenttype",
    "auth.permission",
    "admin.logentry",
    "sessions.session",
    # Users - preserve in production
    "auth.user",
    "quiz.userprofile",
    "account.emailaddress",
    # Sessions - ephemeral, not part of content
    "quiz.gamesession",
    "quiz.sessionteam",
    "quiz.sessionround",
    "quiz.teamanswer",
    # Analytics - imported separately from Google Sheets
    "quiz.gameresult",
    "quiz.playerstats",
    # Site config
    "sites.site",
}


class Command(BaseCommand):
    help = "Seed the database from a fixture if core quiz data is missing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fixture",
            default="quiz/fixtures/content.json",
            help="Fixture path relative to project root (default: quiz/fixtures/content.json)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Load fixture even if quiz data already exists.",
        )
        parser.add_argument(
            "--nullify-owner",
            action="store_true",
            default=True,
            help="Set owner field to null on Game models to avoid FK issues (default: True)",
        )

    def handle(self, *args, **options):
        fixture_name = options["fixture"]
        force = options["force"]
        nullify_owner = options["nullify_owner"]
        fixture_path = Path(settings.BASE_DIR) / fixture_name

        if not fixture_path.exists():
            self.stderr.write(self.style.ERROR(f"Fixture not found: {fixture_path}"))
            return

        game_model = apps.get_model("quiz", "Game")
        question_model = apps.get_model("quiz", "Question")
        category_model = apps.get_model("quiz", "Category")

        has_quiz_data = (
            game_model.objects.exists()
            or question_model.objects.exists()
            or category_model.objects.exists()
        )

        if has_quiz_data and not force:
            self.stdout.write(
                self.style.WARNING("Seed skipped: quiz data already present.")
            )
            return

        fixture_to_load = fixture_path
        if fixture_path.suffix.lower() == ".json":
            with fixture_path.open() as f:
                data = json.load(f)

            if isinstance(data, list):
                filtered = []
                for item in data:
                    model = item.get("model", "")
                    if model in EXCLUDED_MODELS:
                        continue

                    # Nullify owner field on Game models to avoid user FK issues
                    if model == "quiz.game" and nullify_owner:
                        item = dict(item)
                        fields = dict(item.get("fields", {}))
                        fields["owner"] = None
                        item["fields"] = fields

                    filtered.append(item)

                removed = len(data) - len(filtered)
                if removed:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Filtered {removed} non-content records from fixture."
                        )
                    )

                # Always write to temp file to ensure clean loading
                tmp = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".json", delete=False
                )
                with tmp as handle:
                    json.dump(filtered, handle, indent=2)
                    handle.write("\n")
                fixture_to_load = Path(tmp.name)

        self.stdout.write(f"Seeding database from {fixture_to_load}...")
        call_command("loaddata", str(fixture_to_load))

        if fixture_to_load != fixture_path and fixture_to_load.exists():
            fixture_to_load.unlink(missing_ok=True)
        self.stdout.write(self.style.SUCCESS("Seed completed."))
