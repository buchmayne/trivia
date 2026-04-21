import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


# Models that contain developer-created trivia content
CONTENT_MODELS = {
    "quiz.questiontype",
    "quiz.questionround",
    "quiz.category",
    "quiz.game",
    "quiz.question",
    "quiz.answer",
    "quiz.subquestion",
}


class Command(BaseCommand):
    help = "Export content-only models from a fixture, stripping user and session data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--input",
            default="db_initial_data.json",
            help="Source fixture filename at project root (default: db_initial_data.json)",
        )
        parser.add_argument(
            "--output",
            default="quiz/fixtures/content.json",
            help="Output fixture path (default: quiz/fixtures/content.json)",
        )
        parser.add_argument(
            "--nullify-owner",
            action="store_true",
            default=True,
            help="Set owner field to null on Game models (default: True)",
        )

    def handle(self, *args, **options):
        input_path = Path(settings.BASE_DIR) / options["input"]
        output_path = Path(settings.BASE_DIR) / options["output"]

        if not input_path.exists():
            self.stderr.write(self.style.ERROR(f"Input fixture not found: {input_path}"))
            return

        with input_path.open() as f:
            data = json.load(f)

        if not isinstance(data, list):
            self.stderr.write(self.style.ERROR("Fixture must be a JSON array"))
            return

        # Filter to content models only
        filtered = []
        for item in data:
            model = item.get("model", "")
            if model not in CONTENT_MODELS:
                continue

            # Nullify owner field on Game models to avoid user FK issues
            if model == "quiz.game" and options["nullify_owner"]:
                item = dict(item)
                fields = dict(item.get("fields", {}))
                fields["owner"] = None
                item["fields"] = fields

            filtered.append(item)

        # Count by model type
        model_counts = {}
        for item in filtered:
            model = item.get("model", "unknown")
            model_counts[model] = model_counts.get(model, 0) + 1

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w") as f:
            json.dump(filtered, f, indent=2)
            f.write("\n")

        self.stdout.write(
            self.style.SUCCESS(f"Exported {len(filtered)} content records to {output_path}")
        )
        for model, count in sorted(model_counts.items()):
            self.stdout.write(f"  {model}: {count}")

        excluded_count = len(data) - len(filtered)
        self.stdout.write(
            self.style.WARNING(f"Excluded {excluded_count} non-content records")
        )
