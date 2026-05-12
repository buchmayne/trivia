import json
from pathlib import Path

from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand

# Ordered list of content models to export.
# Order matters: dependencies must come before dependents so loaddata works correctly.
CONTENT_MODELS = [
    ("quiz", "QuestionType"),
    ("quiz", "QuestionRound"),
    ("quiz", "Category"),
    ("quiz", "Game"),
    ("quiz", "Question"),
    ("quiz", "Answer"),
]


class Command(BaseCommand):
    help = "Export content-only models from the live database to a fixture file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="quiz/fixtures/content.json",
            help="Output fixture path relative to project root (default: quiz/fixtures/content.json)",
        )
        parser.add_argument(
            "--nullify-owner",
            action="store_true",
            default=True,
            help="Set owner field to null on Game models (default: True)",
        )

    def handle(self, *args, **options):
        from django.apps import apps

        output_path = Path(settings.BASE_DIR) / options["output"]
        nullify_owner = options["nullify_owner"]

        all_records = []
        model_counts = {}

        for app_label, model_name in CONTENT_MODELS:
            model = apps.get_model(app_label, model_name)
            queryset = model.objects.all()

            # Serialize to Python objects so we can mutate before writing
            serialized = json.loads(serializers.serialize("json", queryset))

            # Nullify owner FK on Game records to avoid user FK violations
            # when loading into a fresh environment
            if app_label == "quiz" and model_name == "Game" and nullify_owner:
                for record in serialized:
                    record["fields"]["owner"] = None

            all_records.extend(serialized)
            model_counts[f"{app_label}.{model_name.lower()}"] = len(serialized)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w") as f:
            json.dump(all_records, f, indent=2)
            f.write("\n")

        total = len(all_records)
        self.stdout.write(
            self.style.SUCCESS(f"Exported {total} content records to {output_path}")
        )
        for model_label, count in model_counts.items():
            self.stdout.write(f"  {model_label}: {count}")
