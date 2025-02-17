import hashlib
import json
import os
from django.db import transaction
import pandas as pd
from typing import Dict, Any
from quiz.models import GameResult, PlayerStats, ContentUpdate
from django.conf import settings


class AnalyticsLoader:
    @staticmethod
    @transaction.atomic
    def load_game_results(game_results_df: pd.DataFrame) -> None:
        """
        Load game results from DataFrame to database
        """
        # Convert DataFrame records to list of dicts
        records = game_results_df.to_dict("records")

        # Clear existing records and bulk create new ones
        GameResult.objects.all().delete()
        GameResult.objects.bulk_create([GameResult(**record) for record in records])

    @staticmethod
    @transaction.atomic
    def load_player_stats(career_stats_df: pd.DataFrame) -> None:
        """
        Load player statistics from DataFrame to database
        """
        records = career_stats_df.to_dict("records")

        # Update or create player stats
        PlayerStats.objects.all().delete()
        PlayerStats.objects.bulk_create([PlayerStats(**record) for record in records])


class ContentUtils:
    @staticmethod
    def calculate_checksum(content: str) -> str:
        """Calculate SHA-256 checksum of content"""
        return hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def get_processed_questions(updates_dir: str) -> dict:
        """Load all previously processed questions"""
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
                            key = f"{game_data['game_name']}::{question.get('category')}::{question['question_number']}"
                            processed_questions[key] = question

        return processed_questions
