from django.db import models

class TriviaGame(models.Model):
    game_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    played = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Question(models.Model):
    QUESTION_TYPES = [
        ('RK', 'Ranking'),
    ]

    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    trivia_game = models.ForeignKey(TriviaGame, on_delete=models.CASCADE, related_name='questions')
    question_id = models.AutoField(primary_key=True, unique=True)
    question_type = models.CharField(max_length=2, choices=QUESTION_TYPES)
    question_text = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.question_id}-{self.question_text}"

class RankingQuestion(Question):
    pass

class RankingOption(models.Model):
    question = models.ForeignKey(RankingQuestion, on_delete=models.CASCADE, related_name='options')
    option_text = models.CharField(max_length=255)
    points = models.PositiveIntegerField(default=1)
    correct_rank = models.PositiveIntegerField()
    value_text = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.option_text
    
    class Meta:
        ordering = ['correct_rank']
        unique_together = ['question', 'correct_rank']

