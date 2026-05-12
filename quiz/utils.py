import os
import mimetypes

from django.db import transaction
import pandas as pd

from quiz.models import GameResult, PlayerStats


def has_verified_email(user):
    """Check if user has at least one verified email address."""
    if not user.is_authenticated:
        return False
    return user.emailaddress_set.filter(verified=True).exists()


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


def get_content_type(filename):
    """Get the content type of a file based on its extension"""
    content_type, _ = mimetypes.guess_type(filename)
    if not content_type:
        content_type = "application/octet-stream"  # default behavior is binary data, don't know if this is correct
    return content_type
