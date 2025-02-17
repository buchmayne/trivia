from django.core.management.base import BaseCommand
import json
import os
from datetime import datetime
from django.conf import settings
from quiz.models import Question, ContentUpdate
from django.core.serializers.json import DjangoJSONEncoder
from typing import Dict, Any
import hashlib


class Command(BaseCommand):
    help = "Export new or modified questions"

    def create_question_key(self, game_name, category_name, question_number):
        """Create a unique key for a question"""
        return f"{game_name}::{category_name}::{question_number}"

    def get_question_data(self, question) -> Dict[str, Any]:
        """Create a standardized dictionary of all question data for comparison"""
        data = {
            "text": question.text,
            "answer_bank": question.answer_bank,
            "question_type": question.question_type.name,
            "question_image_url": question.question_image_url,
            "answer_image_url": question.answer_image_url,
            "total_points": question.total_points,
            "category": question.category.name if question.category else None,
            "game_round": (
                {
                    "name": question.game_round.name,
                    "round_number": question.game_round.round_number,
                }
                if question.game_round
                else None
            ),
            "answers": [
                {
                    "text": answer.text,
                    "question_image_url": answer.question_image_url,
                    "display_order": answer.display_order,
                    "correct_rank": answer.correct_rank,
                    "points": answer.points,
                    "answer_text": answer.answer_text,
                    "explanation": answer.explanation,
                    "answer_image_url": answer.answer_image_url,
                }
                for answer in question.answers.all().order_by("id")
            ],
        }
        return data

    def compare_questions(self, db_data: Dict, file_data: Dict) -> bool:
        """Compare question data between database and file versions"""
        # Fields to ignore in comparison
        ignore_fields = {"created_at", "game", "question_number"}

        # Remove fields we don't want to compare
        db_data = {k: v for k, v in db_data.items() if k not in ignore_fields}
        file_data = {k: v for k, v in file_data.items() if k not in ignore_fields}

        # Remove any None or empty values for comparison
        db_data = {k: v for k, v in db_data.items() if v is not None}
        file_data = {k: v for k, v in file_data.items() if v is not None}

        # Compare all fields except answers first
        db_answers = db_data.pop("answers", [])
        file_answers = file_data.pop("answers", [])

        if db_data != file_data:
            self.stdout.write("\nMain data mismatch!")
            for key in set(db_data.keys()) | set(file_data.keys()):
                if db_data.get(key) != file_data.get(key):
                    self.stdout.write(f"Field '{key}' differs:")
                    self.stdout.write(f"  DB: {db_data.get(key)}")
                    self.stdout.write(f"  File: {file_data.get(key)}")
            return False

        # Compare answers if present in both
        if db_answers and file_answers:
            if len(db_answers) != len(file_answers):
                self.stdout.write(
                    f"\nAnswer count mismatch! DB: {len(db_answers)}, File: {len(file_answers)}"
                )
                return False

            for i, (db_ans, file_ans) in enumerate(zip(db_answers, file_answers)):
                db_ans = {k: v for k, v in db_ans.items() if v is not None}
                file_ans = {k: v for k, v in file_ans.items() if v is not None}
                if db_ans != file_ans:
                    self.stdout.write(f"\nAnswer {i} mismatch!")
                    self.stdout.write("DB Answer:")
                    self.stdout.write(json.dumps(db_ans, indent=2))
                    self.stdout.write("File Answer:")
                    self.stdout.write(json.dumps(file_ans, indent=2))
                    return False

        return True

    def load_initial_data(self) -> Dict[str, Dict]:
        """Load questions from initial data file"""
        questions = {}
        try:
            with open("db_initial_data.json", "r") as f:
                data = json.load(f)

            # Create lookup tables
            game_lookup = {
                entry["pk"]: entry["fields"]["name"]
                for entry in data
                if entry["model"] == "quiz.game"
            }
            category_lookup = {
                entry["pk"]: entry["fields"]["name"]
                for entry in data
                if entry["model"] == "quiz.category"
            }
            question_type_lookup = {
                entry["pk"]: entry["fields"]["name"]
                for entry in data
                if entry["model"] == "quiz.questiontype"
            }
            round_lookup = {
                entry["pk"]: {
                    "name": entry["fields"]["name"],
                    "round_number": entry["fields"]["round_number"],
                }
                for entry in data
                if entry["model"] == "quiz.questionround"
            }

            for entry in data:
                if entry["model"] == "quiz.question":
                    fields = entry["fields"]
                    game_name = game_lookup.get(fields["game"])
                    category_name = category_lookup.get(fields.get("category"))
                    key = self.create_question_key(
                        game_name, category_name, fields["question_number"]
                    )

                    # Convert IDs to names/objects
                    questions[key] = {
                        "text": fields["text"],
                        "answer_bank": fields.get("answer_bank", ""),
                        "question_type": question_type_lookup.get(
                            fields["question_type"]
                        ),
                        "question_image_url": fields.get("question_image_url"),
                        "answer_image_url": fields.get("answer_image_url"),
                        "total_points": fields.get("total_points", 1),
                        "category": category_lookup.get(fields.get("category")),
                        "game_round": round_lookup.get(fields.get("game_round")),
                    }

        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"Error reading initial data: {str(e)}")
            )

        return questions

    def load_processed_updates(self, updates_dir: str) -> Dict[str, Dict]:
        """Load questions from processed content updates"""
        processed_questions = {}

        for update in ContentUpdate.objects.filter(processed=True).order_by(
            "timestamp"
        ):
            filepath = os.path.join(updates_dir, update.filename)
            if os.path.exists(filepath):
                with open(filepath, "r") as f:
                    data = json.load(f)
                    for game_data in data.get("question_groups", []):
                        for question in game_data.get("questions", []):
                            key = self.create_question_key(
                                game_data["game_name"],
                                question.get("category"),
                                question["question_number"],
                            )
                            processed_questions[key] = question

        return processed_questions

    def handle(self, *args, **options):
        # Create content_updates directory if it doesn't exist
        updates_dir = os.path.join(settings.BASE_DIR, "content_updates")
        if not os.path.exists(updates_dir):
            os.makedirs(updates_dir)

        # Get questions from initial data and processed updates
        initial_questions = self.load_initial_data()
        processed_questions = self.load_processed_updates(updates_dir)

        # Combine initial and processed questions, with processed taking precedence
        all_existing_questions = {**initial_questions, **processed_questions}

        self.stdout.write(
            f"Found {len(initial_questions)} questions in initial data and "
            f"{len(processed_questions)} questions in processed updates"
        )

        # Get all questions from database and compare
        modified_questions = []
        for question in Question.objects.select_related(
            "game", "category", "question_type", "game_round"
        ).prefetch_related("answers"):
            key = self.create_question_key(
                question.game.name,
                question.category.name if question.category else None,
                question.question_number,
            )

            db_data = self.get_question_data(question)

            if key not in all_existing_questions:
                modified_questions.append(question)
                self.stdout.write(f"New question found: {key}")
            else:
                if not self.compare_questions(db_data, all_existing_questions[key]):
                    modified_questions.append(question)
                    self.stdout.write(f"Modified question found: {key}")

        if not modified_questions:
            self.stdout.write("No new or modified questions found")
            return

        # Group questions by game
        games_data = {}
        for question in modified_questions:
            if question.game.name not in games_data:
                games_data[question.game.name] = {
                    "game_name": question.game.name,
                    "game_description": question.game.description,
                    "is_password_protected": question.game.is_password_protected,
                    "password": question.game.password,
                    "game_order": question.game.game_order,
                    "questions": [],
                }

            # Build question data
            question_data = {
                "text": question.text,
                "answer_bank": question.answer_bank,
                "question_type": question.question_type.name,
                "question_image_url": question.question_image_url,
                "answer_image_url": question.answer_image_url,
                "question_number": question.question_number,
                "total_points": question.total_points,
            }

            if question.category:
                question_data["category"] = question.category.name

            if question.game_round:
                question_data["round"] = {
                    "name": question.game_round.name,
                    "round_number": question.game_round.round_number,
                }

            question_data["answers"] = []
            for answer in question.answers.all():
                answer_data = {
                    "text": answer.text,
                    "question_image_url": answer.question_image_url,
                    "display_order": answer.display_order,
                    "correct_rank": answer.correct_rank,
                    "points": answer.points,
                    "answer_text": answer.answer_text,
                    "explanation": answer.explanation,
                    "answer_image_url": answer.answer_image_url,
                }
                question_data["answers"].append(answer_data)

            games_data[question.game.name]["questions"].append(question_data)

        # Create the update file
        timestamp = datetime.now().strftime("%Y_%m_%d_%H%M")
        filename = f"content_update_{timestamp}.json"
        filepath = os.path.join(updates_dir, filename)

        # Write the file and create ContentUpdate record
        update_data = {"question_groups": list(games_data.values())}
        content = json.dumps(update_data, indent=2, cls=DjangoJSONEncoder)

        with open(filepath, "w") as f:
            f.write(content)

        # Create ContentUpdate record
        ContentUpdate.objects.create(
            filename=filename,
            checksum=hashlib.sha256(content.encode()).hexdigest(),
            question_count=len(modified_questions),
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully exported {sum(len(g["questions"]) for g in games_data.values())} '
                f"questions from {len(games_data)} games to {filename}"
            )
        )
