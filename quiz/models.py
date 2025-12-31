from django.db import models
from django.utils import timezone
from tinymce.models import HTMLField
from .fields import CloudFrontURLField, S3ImageField, S3VideoField
import secrets
import random
import string


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


# SESSION MODELS - Live multiplayer game sessions


class GameSession(models.Model):
    """A live game session where teams compete"""

    class Status(models.TextChoices):
        LOBBY = "lobby", "Waiting for Teams"
        PLAYING = "playing", "Game in Progress"
        PAUSED = "paused", "Paused (Admin Disconnected)"
        SCORING = "scoring", "Scoring Round"
        COMPLETED = "completed", "Game Completed"

    code = models.CharField(max_length=6, unique=True, db_index=True)
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="sessions")
    admin_name = models.CharField(max_length=100)
    admin_token = models.CharField(
        max_length=64, unique=True, default=secrets.token_urlsafe
    )

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.LOBBY
    )
    status_before_pause = models.CharField(
        max_length=20, null=True, blank=True
    )  # For resume after disconnect

    current_question = models.ForeignKey(
        Question, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    current_round = models.ForeignKey(
        QuestionRound,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    max_teams = models.PositiveIntegerField(default=16)
    allow_late_joins = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    admin_last_seen = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.code} - {self.game.name}"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._generate_unique_code()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_unique_code():
        """Generate a unique 6-character session code"""
        while True:
            code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not GameSession.objects.filter(code=code).exists():
                return code

    def pause(self):
        """Pause session (admin disconnect)."""
        if self.status not in [self.Status.COMPLETED, self.Status.PAUSED]:
            self.status_before_pause = self.status
            self.status = self.Status.PAUSED
            self.save()

    def resume(self):
        """Resume session (admin reconnect)."""
        if self.status == self.Status.PAUSED and self.status_before_pause:
            self.status = self.status_before_pause
            self.status_before_pause = None
            self.save()


class SessionTeam(models.Model):
    """A team participating in a game session"""

    session = models.ForeignKey(
        GameSession, on_delete=models.CASCADE, related_name="teams"
    )
    name = models.CharField(max_length=100)
    token = models.CharField(max_length=64, unique=True, default=secrets.token_urlsafe)
    score = models.IntegerField(default=0)

    joined_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    joined_late = models.BooleanField(
        default=False
    )  # True if joined after game started

    class Meta:
        unique_together = ["session", "name"]
        ordering = ["-score", "joined_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.session.code})"


class SessionRound(models.Model):
    """Tracks round state within a session"""

    class Status(models.TextChoices):
        PENDING = "pending", "Not Started"
        ACTIVE = "active", "In Progress"
        LOCKED = "locked", "Answers Locked"
        SCORED = "scored", "Scoring Complete"

    session = models.ForeignKey(
        GameSession, on_delete=models.CASCADE, related_name="session_rounds"
    )
    round = models.ForeignKey(QuestionRound, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )

    started_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    scored_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["session", "round"]
        ordering = ["round__round_number"]

    def __str__(self) -> str:
        return f"{self.session.code} - {self.round.name}"


class TeamAnswer(models.Model):
    """A team's answer to a question"""

    team = models.ForeignKey(
        SessionTeam, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    session_round = models.ForeignKey(
        SessionRound, on_delete=models.CASCADE, related_name="answers"
    )

    answer_text = models.TextField(blank=True, default="")
    is_locked = models.BooleanField(default=False)

    # Scoring: null means not yet scored, value is admin-assigned points
    points_awarded = models.IntegerField(null=True, blank=True)
    scored_at = models.DateTimeField(null=True, blank=True)

    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["team", "question"]
        indexes = [
            models.Index(fields=["session_round", "team"]),
        ]

    def __str__(self) -> str:
        return f"{self.team.name} - Q{self.question.question_number}"
