from django.db import models
from django.utils import timezone
from tinymce.models import HTMLField


class Game(models.Model):
    name = models.CharField(max_length=255)
    description = HTMLField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    # Adding password protection
    is_password_protected = models.BooleanField(default=False)
    password = models.CharField(max_length=50, blank=True, null=True)

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

    question_image_url = models.URLField(blank=True, null=True)
    answer_image_url = models.URLField(blank=True, null=True)

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
    question_image_url = models.URLField(blank=True, null=True)
    is_correct = models.BooleanField(default=False)

    # These fields are mainly relevant for ranking questions
    display_order = models.PositiveIntegerField(null=True, blank=True)
    correct_rank = models.PositiveIntegerField(null=True, blank=True)

    # Points field is general for all question types
    points = models.PositiveIntegerField(default=1)

    # New fields for answer details:
    answer_text = models.CharField(max_length=255, blank=True, null=True)
    explanation = models.TextField(blank=True, null=True)
    answer_image_url = models.URLField(blank=True, null=True)

    def __str__(self) -> str:
        return self.text if self.text else f"Answer for {self.question}"
