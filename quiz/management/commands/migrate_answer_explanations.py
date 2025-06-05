from django.core.management.base import BaseCommand
from quiz.models import Question, Answer, QuestionType
from django.db import transaction


class Command(BaseCommand):
    help = "Migrate answer explanations to answer text field for Ranking questions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without making changes",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Get the Ranking question type
        try:
            ranking_type = QuestionType.objects.get(name="Ranking")
        except QuestionType.DoesNotExist:
            self.stdout.write(self.style.ERROR("Question type 'Ranking' not found."))
            return

        # Find all ranking questions
        ranking_questions = Question.objects.filter(question_type=ranking_type)
        self.stdout.write(f"Found {ranking_questions.count()} ranking questions.")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        # Statistics
        total_answers = 0
        would_migrate = 0
        would_skip_empty = 0
        would_skip_conflict = 0

        # Process each question's answers
        for question in ranking_questions:
            answers = Answer.objects.filter(question=question)
            total_answers += answers.count()

            for answer in answers:
                if not answer.explanation:
                    would_skip_empty += 1
                    self.stdout.write(
                        f"Would skip answer #{answer.id} (no explanation)"
                    )
                    continue

                if answer.answer_text and answer.answer_text != answer.explanation:
                    # Potential conflict - text field already has data that's different
                    would_skip_conflict += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"CONFLICT for answer #{answer.id}: "
                            f"Answer Text: '{answer.answer_text}', "
                            f"Explanation: '{answer.explanation}'"
                        )
                    )
                    continue

                # Otherwise, we can migrate
                would_migrate += 1
                self.stdout.write(
                    f"Would migrate answer #{answer.id}: "
                    f"Explanation -> Text: '{answer.explanation}'"
                )

                if not dry_run:
                    with transaction.atomic():
                        answer.answer_text = answer.explanation
                        answer.save(update_fields=["answer_text"])

        # Print summary
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"DRY RUN SUMMARY:\n"
                    f"Total answers for ranking questions: {total_answers}\n"
                    f"Would migrate: {would_migrate}\n"
                    f"Would skip (empty explanation): {would_skip_empty}\n"
                    f"Would skip (potential conflict): {would_skip_conflict}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"MIGRATION COMPLETE:\n"
                    f"Total answers for ranking questions: {total_answers}\n"
                    f"Migrated: {would_migrate}\n"
                    f"Skipped (empty explanation): {would_skip_empty}\n"
                    f"Skipped (potential conflict): {would_skip_conflict}"
                )
            )
