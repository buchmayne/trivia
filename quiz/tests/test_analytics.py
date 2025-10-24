"""
Tests for quiz/analytics.py and quiz/utils.py - Analytics and utility functions
"""
from django.test import TestCase
from unittest.mock import patch, MagicMock
import pandas as pd
from quiz.models import GameResult, PlayerStats
from quiz.utils import AnalyticsLoader


class AnalyticsLoaderTest(TestCase):
    """Test the AnalyticsLoader utility class"""

    def setUp(self):
        self.loader = AnalyticsLoader()

    def test_load_game_results(self):
        """Test loading game results from DataFrame to database"""
        # Create sample DataFrame
        data = {
            "game_date": ["2024-01-01", "2024-01-01"],
            "players": ["Alice, Bob", "Charlie, Dave"],
            "place": [1, 2],
            "winner": [True, False],
            "Round_1": [30, 25],
            "Round_2": [40, 35],
            "Final": [20, 15],
            "Total": [90, 75],
            "pct_rd1": [0.85, 0.70],
            "pct_rd2": [0.90, 0.80],
            "pct_final": [0.95, 0.75],
            "pct_total": [0.88, 0.73],
            "normalized_total": [1.0, 0.83],
            "zscore_total": [1.5, -0.5],
        }
        df = pd.DataFrame(data)

        # Load the data
        self.loader.load_game_results(df)

        # Verify data was loaded
        self.assertEqual(GameResult.objects.count(), 2)

        # Verify first record
        result1 = GameResult.objects.get(place=1)
        self.assertEqual(result1.players, "Alice, Bob")
        self.assertEqual(result1.Total, 90)
        self.assertTrue(result1.winner)

    def test_load_game_results_clears_existing(self):
        """Test that loading new results clears existing data"""
        # Create initial data
        GameResult.objects.create(
            game_date="2023-01-01",
            players="Old Data",
            place=1,
            winner=True,
            Round_1=10,
            Round_2=10,
            Final=10,
            Total=30,
            pct_rd1=0.5,
            pct_rd2=0.5,
            pct_final=0.5,
            pct_total=0.5,
            normalized_total=1.0,
            zscore_total=0.0,
        )

        self.assertEqual(GameResult.objects.count(), 1)

        # Load new data
        data = {
            "game_date": ["2024-01-01"],
            "players": ["New Data"],
            "place": [1],
            "winner": [True],
            "Round_1": [20],
            "Round_2": [20],
            "Final": [20],
            "Total": [60],
            "pct_rd1": [0.8],
            "pct_rd2": [0.8],
            "pct_final": [0.8],
            "pct_total": [0.8],
            "normalized_total": [1.0],
            "zscore_total": [0.0],
        }
        df = pd.DataFrame(data)

        self.loader.load_game_results(df)

        # Verify old data was replaced
        self.assertEqual(GameResult.objects.count(), 1)
        result = GameResult.objects.first()
        self.assertEqual(result.players, "New Data")

    def test_load_player_stats(self):
        """Test loading player statistics from DataFrame to database"""
        # Create sample DataFrame
        data = {
            "player": ["Alice", "Bob"],
            "avg_final_place": [1.5, 2.0],
            "total_wins": [3, 2],
            "avg_zscore_total_points": [0.8, 0.5],
            "avg_total_points": [85.5, 80.0],
            "avg_pct_total_points": [0.85, 0.80],
            "avg_normalized_total_points": [0.90, 0.85],
            "avg_pct_rd1_points": [0.82, 0.78],
            "avg_pct_rd2_points": [0.88, 0.82],
            "avg_pct_final_rd_points": [0.90, 0.85],
            "games_played": [5, 4],
        }
        df = pd.DataFrame(data)

        # Load the data
        self.loader.load_player_stats(df)

        # Verify data was loaded
        self.assertEqual(PlayerStats.objects.count(), 2)

        # Verify Alice's stats
        alice_stats = PlayerStats.objects.get(player="Alice")
        self.assertEqual(alice_stats.total_wins, 3)
        self.assertEqual(alice_stats.games_played, 5)
        self.assertEqual(alice_stats.avg_final_place, 1.5)

    def test_load_player_stats_clears_existing(self):
        """Test that loading new stats clears existing data"""
        # Create initial data
        PlayerStats.objects.create(
            player="Old Player",
            avg_final_place=1.0,
            total_wins=10,
            avg_zscore_total_points=1.0,
            avg_total_points=90.0,
            avg_pct_total_points=0.90,
            avg_normalized_total_points=0.95,
            avg_pct_rd1_points=0.88,
            avg_pct_rd2_points=0.90,
            avg_pct_final_rd_points=0.92,
            games_played=20,
        )

        self.assertEqual(PlayerStats.objects.count(), 1)

        # Load new data
        data = {
            "player": ["New Player"],
            "avg_final_place": [2.0],
            "total_wins": [5],
            "avg_zscore_total_points": [0.5],
            "avg_total_points": [80.0],
            "avg_pct_total_points": [0.80],
            "avg_normalized_total_points": [0.85],
            "avg_pct_rd1_points": [0.78],
            "avg_pct_rd2_points": [0.80],
            "avg_pct_final_rd_points": [0.82],
            "games_played": [10],
        }
        df = pd.DataFrame(data)

        self.loader.load_player_stats(df)

        # Verify old data was replaced
        self.assertEqual(PlayerStats.objects.count(), 1)
        stats = PlayerStats.objects.first()
        self.assertEqual(stats.player, "New Player")

    def test_load_empty_dataframe(self):
        """Test loading an empty DataFrame"""
        # Create empty DataFrames with correct columns
        game_results_df = pd.DataFrame(
            columns=[
                "game_date",
                "players",
                "place",
                "winner",
                "Round_1",
                "Round_2",
                "Final",
                "Total",
                "pct_rd1",
                "pct_rd2",
                "pct_final",
                "pct_total",
                "normalized_total",
                "zscore_total",
            ]
        )
        player_stats_df = pd.DataFrame(
            columns=[
                "player",
                "avg_final_place",
                "total_wins",
                "avg_zscore_total_points",
                "avg_total_points",
                "avg_pct_total_points",
                "avg_normalized_total_points",
                "avg_pct_rd1_points",
                "avg_pct_rd2_points",
                "avg_pct_final_rd_points",
                "games_played",
            ]
        )

        # Should not raise errors
        self.loader.load_game_results(game_results_df)
        self.loader.load_player_stats(player_stats_df)

        self.assertEqual(GameResult.objects.count(), 0)
        self.assertEqual(PlayerStats.objects.count(), 0)


class AnalyticsUtilsTest(TestCase):
    """Test utility functions in utils.py"""

    def test_get_content_type_image(self):
        """Test get_content_type for image files"""
        from quiz.utils import get_content_type

        self.assertEqual(get_content_type("image.jpg"), "image/jpeg")
        self.assertEqual(get_content_type("photo.png"), "image/png")
        self.assertEqual(get_content_type("graphic.gif"), "image/gif")

    def test_get_content_type_video(self):
        """Test get_content_type for video files"""
        from quiz.utils import get_content_type

        self.assertEqual(get_content_type("video.mp4"), "video/mp4")
        self.assertEqual(get_content_type("clip.avi"), "video/x-msvideo")
        self.assertEqual(get_content_type("movie.mov"), "video/quicktime")

    def test_get_content_type_unknown(self):
        """Test get_content_type for unknown file types"""
        from quiz.utils import get_content_type

        # Should return default for unknown extensions
        result = get_content_type("file.xyz")
        self.assertEqual(result, "application/octet-stream")

    def test_get_content_type_no_extension(self):
        """Test get_content_type for files without extension"""
        from quiz.utils import get_content_type

        result = get_content_type("filename")
        self.assertEqual(result, "application/octet-stream")


class GameResultModelTest(TestCase):
    """Test the GameResult model"""

    def test_create_game_result(self):
        """Test creating a game result"""
        result = GameResult.objects.create(
            game_date="2024-01-01",
            players="Alice, Bob",
            place=1,
            winner=True,
            Round_1=30,
            Round_2=40,
            Final=20,
            Total=90,
            pct_rd1=0.85,
            pct_rd2=0.90,
            pct_final=0.95,
            pct_total=0.88,
            normalized_total=1.0,
            zscore_total=1.5,
        )

        self.assertEqual(result.players, "Alice, Bob")
        self.assertEqual(result.Total, 90)
        self.assertTrue(result.winner)

    def test_game_result_unique_constraint(self):
        """Test unique constraint on game_date and players"""
        GameResult.objects.create(
            game_date="2024-01-01",
            players="Alice, Bob",
            place=1,
            winner=True,
            Round_1=30,
            Round_2=40,
            Final=20,
            Total=90,
            pct_rd1=0.85,
            pct_rd2=0.90,
            pct_final=0.95,
            pct_total=0.88,
            normalized_total=1.0,
            zscore_total=1.5,
        )

        # Should raise IntegrityError for duplicate
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                GameResult.objects.create(
                    game_date="2024-01-01",
                    players="Alice, Bob",
                    place=2,
                    winner=False,
                    Round_1=25,
                    Round_2=35,
                    Final=15,
                    Total=75,
                    pct_rd1=0.70,
                    pct_rd2=0.80,
                    pct_final=0.75,
                    pct_total=0.73,
                    normalized_total=0.83,
                    zscore_total=-0.5,
                )


class PlayerStatsModelTest(TestCase):
    """Test the PlayerStats model"""

    def test_create_player_stats(self):
        """Test creating player statistics"""
        stats = PlayerStats.objects.create(
            player="Alice",
            avg_final_place=1.5,
            total_wins=3,
            avg_zscore_total_points=0.8,
            avg_total_points=85.5,
            avg_pct_total_points=0.85,
            avg_normalized_total_points=0.90,
            avg_pct_rd1_points=0.82,
            avg_pct_rd2_points=0.88,
            avg_pct_final_rd_points=0.90,
            games_played=5,
        )

        self.assertEqual(stats.player, "Alice")
        self.assertEqual(stats.total_wins, 3)
        self.assertEqual(stats.games_played, 5)
        self.assertAlmostEqual(stats.avg_final_place, 1.5)

    def test_player_stats_calculations(self):
        """Test that player stats store calculated values correctly"""
        stats = PlayerStats.objects.create(
            player="Bob",
            avg_final_place=2.0,
            total_wins=2,
            avg_zscore_total_points=0.5,
            avg_total_points=80.0,
            avg_pct_total_points=0.80,
            avg_normalized_total_points=0.85,
            avg_pct_rd1_points=0.78,
            avg_pct_rd2_points=0.82,
            avg_pct_final_rd_points=0.85,
            games_played=4,
        )

        # Verify all percentages are stored correctly
        self.assertAlmostEqual(stats.avg_pct_rd1_points, 0.78)
        self.assertAlmostEqual(stats.avg_pct_rd2_points, 0.82)
        self.assertAlmostEqual(stats.avg_pct_final_rd_points, 0.85)
