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
    name = models.CharField(max_length=100, unique=True, primary_key=True)

    def __str__(self):
        return self.name


class Question(models.Model):
    QUESTION_TYPES = [
        ('RK', 'Ranking'),
    ]

    question_id = models.AutoField(primary_key=True, unique=True)
    
    trivia_game = models.ForeignKey(TriviaGame, on_delete=models.CASCADE, related_name='questions')
    category = models.ForeignKey(Category, on_delete=models.CASCADE)

    question_type = models.CharField(max_length=30, choices=QUESTION_TYPES)
    question_text = models.CharField(max_length=200)

    # how to add images or other media files to the question?

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

