from django.db import transaction
import pandas as pd
from quiz.models import GameResult, PlayerStats


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
