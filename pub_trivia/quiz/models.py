from django.db import models
from django.utils import timezone

class Game(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)  # Add this field

    def __str__(self):
        return self.name

class Category(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name}"

class QuestionType(models.Model):
    name = models.CharField(max_length=255)  # e.g., "Multiple Choice", "Ranking", "Matching"
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Question(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='questions')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    question_type = models.ForeignKey(QuestionType, on_delete=models.CASCADE, related_name='questions')
    points = models.IntegerField(default=1)
    image_url = models.URLField(blank=True, null=True)
    question_number = models.IntegerField()  # Sequential question number for the entire game
    created_at = models.DateTimeField(auto_now_add=True)
    total_points = models.PositiveIntegerField(default=1)  # Total points for the question

    class Meta:
        unique_together = ['game', 'question_number']  # Ensure question numbers are unique within a game

    def __str__(self):
        return f"Q{self.question_number}: {self.text}"


class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    text = models.TextField(blank=True, null=True)  # For textual answers
    image_url = models.URLField(blank=True, null=True)
    is_correct = models.BooleanField(default=False)  # Used for simple questions, can be expanded for others

    # These fields are mainly relevant for ranking questions
    display_order = models.PositiveIntegerField(null=True, blank=True)  # Optional, used for specifying order
    correct_rank = models.PositiveIntegerField(null=True, blank=True)   # Optional, used only for ranking questions
    
    # Points field is general for all question types
    points = models.PositiveIntegerField(default=1)  # Points for each answer, usable across different question types

    # New fields for answer details:
    answer_text = models.CharField(max_length=255, blank=True, null=True)  # Actual value (e.g., coffee consumption, statue height)
    explanation = models.TextField(blank=True, null=True)  # Explanation or answer details


    def __str__(self):
        return self.text if self.text else f"Answer for {self.question}"

