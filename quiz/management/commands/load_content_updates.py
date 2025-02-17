from django.core.management.base import BaseCommand
import json
import os
from django.conf import settings
from quiz.models import (
    Question,
    Game,
    Category,
    QuestionType,
    QuestionRound,
    ContentUpdate,
)
from django.db import transaction
from django.utils import timezone
import hashlib


class Command(BaseCommand):
    help = "Load content updates from the content_updates directory"

    def calculate_checksum(self, content: str) -> str:
        """Calculate SHA-256 checksum of content"""
        return hashlib.sha256(content.encode()).hexdigest()

    def process_question_data(self, game_data):
        """Process a game's question data and create/update database records"""
        game, _ = Game.objects.get_or_create(
            name=game_data["game_name"],
            defaults={
                "description": game_data.get("game_description", ""),
                "is_password_protected": game_data.get("is_password_protected", False),
                "password": game_data.get("password"),
                "game_order": game_data.get("game_order", 1),
            },
        )

        for question_data in game_data.get("questions", []):
            # Get or create category if specified
            category = None
            if question_data.get("category"):
                category, _ = Category.objects.get_or_create(
                    name=question_data["category"]
                )
                game.categories.add(category)

            # Get or create question type
            question_type, _ = QuestionType.objects.get_or_create(
                name=question_data["question_type"]
            )

            # Get or create round if specified
            game_round = None
            if question_data.get("round"):
                game_round, _ = QuestionRound.objects.get_or_create(
                    name=question_data["round"]["name"],
                    defaults={
                        "round_number": question_data["round"].get("round_number", 1)
                    },
                )

            # Get or create question
            question, created = Question.objects.get_or_create(
                game=game,
                question_number=question_data["question_number"],
                defaults={
                    "category": category,
                    "text": question_data["text"],
                    "answer_bank": question_data.get("answer_bank"),
                    "question_type": question_type,
                    "question_image_url": question_data.get("question_image_url"),
                    "answer_image_url": question_data.get("answer_image_url"),
                    "total_points": question_data.get("total_points", 1),
                    "game_round": game_round,
                },
            )

            if not created:
                # Update existing question fields
                question.category = category
                question.text = question_data["text"]
                question.answer_bank = question_data.get("answer_bank")
                question.question_type = question_type
                question.question_image_url = question_data.get("question_image_url")
                question.answer_image_url = question_data.get("answer_image_url")
                question.total_points = question_data.get("total_points", 1)
                question.game_round = game_round
                question.save()

                # Delete existing answers
                question.answers.all().delete()

            # Create answers
            for answer_data in question_data.get("answers", []):
                question.answers.create(
                    text=answer_data.get("text"),
                    question_image_url=answer_data.get("question_image_url"),
                    display_order=answer_data.get("display_order"),
                    correct_rank=answer_data.get("correct_rank"),
                    points=answer_data.get("points", 1),
                    answer_text=answer_data.get("answer_text"),
                    explanation=answer_data.get("explanation"),
                    answer_image_url=answer_data.get("answer_image_url"),
                )

    def handle(self, *args, **options):
        updates_dir = os.path.join(settings.BASE_DIR, "content_updates")

        if not os.path.exists(updates_dir):
            os.makedirs(updates_dir)
            self.stdout.write("Created content_updates directory")
            return

        # Load all unprocessed updates in order of timestamp
        for update in ContentUpdate.objects.filter(processed=False).order_by(
            "timestamp"
        ):
            filepath = os.path.join(updates_dir, update.filename)

            if not os.path.exists(filepath):
                self.stderr.write(f"File not found: {update.filename}")
                continue

            # Verify file integrity
            with open(filepath, "r") as f:
                content = f.read()
                if self.calculate_checksum(content) != update.checksum:
                    self.stderr.write(f"Checksum mismatch for {update.filename}")
                    continue

                data = json.loads(content)

            try:
                with transaction.atomic():
                    # Process each game's questions
                    for game_data in data.get("question_groups", []):
                        self.process_question_data(game_data)

                    # Mark update as processed
                    update.processed = True
                    update.processed_at = timezone.now()
                    update.save()

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully processed {update.filename} with "
                            f"{sum(len(g['questions']) for g in data['question_groups'])} questions"
                        )
                    )

            except Exception as e:
                self.stderr.write(f"Error processing {update.filename}: {str(e)}")
                raise
