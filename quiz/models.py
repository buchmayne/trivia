from django.db import models
from django.utils import timezone
from tinymce.models import HTMLField
from .fields import CloudFrontURLField, S3ImageField, S3VideoField


class Game(models.Model):
    name = models.CharField(max_length=255)
    description = HTMLField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    # Adding password protection
    is_password_protected = models.BooleanField(default=False)
    password = models.CharField(max_length=50, blank=True, null=True)

    game_order = models.IntegerField(default=1, null=True, blank=True)

    def __str__(self) -> str:
        return self.name


class Category(models.Model):
    games = models.ManyToManyField(Game, related_name="categories", blank=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    def __str__(self) -> str:
        return f"{self.name}"


class QuestionType(models.Model):
    name = models.CharField(
        max_length=255
    )  # e.g., "Multiple Choice", "Ranking", "Matching"
    description = models.TextField(blank=True, null=True)

    def __str__(self) -> str:
        return self.name


class QuestionRound(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    round_number = models.IntegerField(default=1)

    class Meta:
        ordering = ["round_number"]

    def __str__(self) -> str:
        return self.name


class Question(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="questions")
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="questions",
        blank=True,
        null=True,
    )

    text = models.TextField()
    answer_bank = models.TextField(blank=True, null=True)

    question_type = models.ForeignKey(
        QuestionType, on_delete=models.CASCADE, related_name="questions"
    )

    question_image_url = CloudFrontURLField(blank=True, null=True)
    answer_image_url = CloudFrontURLField(blank=True, null=True)

    question_image = S3ImageField(blank=True, null=True)
    answer_image = S3ImageField(blank=True, null=True)

    # Video fields
    question_video_url = CloudFrontURLField(blank=True, null=True)
    answer_video_url = CloudFrontURLField(blank=True, null=True)

    question_video = S3VideoField(blank=True, null=True)
    answer_video = S3VideoField(blank=True, null=True)

    question_number = (
        models.IntegerField()
    )  # Sequential question number for the entire game

    created_at = models.DateTimeField(auto_now_add=True)

    total_points = models.PositiveIntegerField(
        default=1
    )  # Total points for the question
    game_round = models.ForeignKey(
        QuestionRound,
        on_delete=models.CASCADE,
        related_name="questions",
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = ["game", "question_number"]

    def __str__(self) -> str:
        return f"Q{self.question_number}: {self.text}"


class Answer(models.Model):
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="answers"
    )
    text = models.TextField(blank=True, null=True)

    # These fields are mainly relevant for ranking questions
    display_order = models.PositiveIntegerField(null=True, blank=True)
    correct_rank = models.PositiveIntegerField(null=True, blank=True)

    # Points field is general for all question types
    points = models.PositiveIntegerField(default=1)

    # New fields for answer details:
    answer_text = models.CharField(max_length=255, blank=True, null=True)

    question_image_url = CloudFrontURLField(blank=True, null=True)
    answer_image_url = CloudFrontURLField(blank=True, null=True)

    question_image = S3ImageField(blank=True, null=True)
    answer_image = S3ImageField(blank=True, null=True)

    # Video fields
    question_video_url = CloudFrontURLField(blank=True, null=True)
    answer_video_url = CloudFrontURLField(blank=True, null=True)

    question_video = S3VideoField(blank=True, null=True)
    answer_video = S3VideoField(blank=True, null=True)

    def __str__(self) -> str:
        return self.text if self.text else f"Answer for {self.question}"

    class Meta:
        ordering = ["display_order", "id"]

    def save(self, *args, **kwargs):
        # If display_order is not set, set it based on the highest existing order + 1
        if self.display_order is None:
            max_order = (
                Answer.objects.filter(question=self.question).aggregate(
                    max_order=models.Max("display_order")
                )["max_order"]
                or 0
            )
            self.display_order = max_order + 1

        super().save(*args, **kwargs)


# ANALYTICS MODELS
class GameResult(models.Model):
    game_date = models.DateField()
    players = models.CharField(max_length=300)
    place = models.IntegerField()
    winner = models.BooleanField()
    Round_1 = models.IntegerField()
    Round_2 = models.IntegerField()
    Final = models.IntegerField()
    Total = models.IntegerField()
    pct_rd1 = models.FloatField()
    pct_rd2 = models.FloatField()
    pct_final = models.FloatField()
    pct_total = models.FloatField()
    normalized_total = models.FloatField()
    zscore_total = models.FloatField()

    class Meta:
        unique_together = ["game_date", "players"]


class PlayerStats(models.Model):
    player = models.CharField(max_length=100)
    avg_final_place = models.FloatField()
    total_wins = models.IntegerField()
    avg_zscore_total_points = models.FloatField()
    avg_total_points = models.FloatField()
    avg_pct_total_points = models.FloatField()
    avg_normalized_total_points = models.FloatField()
    avg_pct_rd1_points = models.FloatField()
    avg_pct_rd2_points = models.FloatField()
    avg_pct_final_rd_points = models.FloatField()
    games_played = models.IntegerField()


# API for Session Models
class GameSession(models.Model):
    session_code = models.CharField(max_length=8, unique=True)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    host_name = models.CharField(max_length=100)
    status = models.CharField(
        max_length=20,
        choices=[
            ("waiting", "Waiting for Teams"),
            ("active", "Game Active"),
            ("paused", "Paused"),
            ("completed", "Completed"),
        ],
        default="waiting",
    )
    current_question_number = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    max_teams = models.IntegerField(default=16)


class SessionTeam(models.Model):
    session = models.ForeignKey(
        GameSession, on_delete=models.CASCADE, related_name="teams"
    )
    team_name = models.CharField(max_length=100)
    total_score = models.IntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["session", "team_name"]


class TeamAnswer(models.Model):
    team = models.ForeignKey(SessionTeam, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    submitted_answer = models.TextField()
    points_awarded = models.IntegerField(default=0)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["team", "question"]
