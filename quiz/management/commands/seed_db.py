import json
import tempfile
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed the database from a fixture if core quiz data is missing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fixture",
            default="db_initial_data.json",
            help="Fixture filename located at the project root.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Load fixture even if quiz data already exists.",
        )

    def handle(self, *args, **options):
        fixture_name = options["fixture"]
        force = options["force"]
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
            blocklist = {
                "contenttypes.contenttype",
                "auth.permission",
                "admin.logentry",
                "sessions.session",
            }
            with fixture_path.open() as f:
                data = json.load(f)

            if isinstance(data, list):
                filtered = [item for item in data if item.get("model") not in blocklist]
                removed = len(data) - len(filtered)
                if removed:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Filtered {removed} system records from fixture."
                        )
                    )
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
