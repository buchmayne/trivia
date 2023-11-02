from django.db import models

class Question(models.Model):
    question_text = models.CharField(max_length=1000)
    question_type = models.CharField(max_length=1000)
    category = models.CharField(max_length=1000)
    game_id = models.CharField(max_length=1000)
    has_been_used = models.BooleanField(default=True)
    question_number = models.IntegerField()
    points = models.IntegerField()
    points_application = models.CharField(max_length=1000)

    def __str__(self):
        return self.question_text

class ChoicesSingleSlideMultipleChoiceNoAnswerBankQuestion(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    choice_text = models.CharField(max_length=1000)
    choice_answer = models.CharField(max_length=1000)

    def __str__(self):
        return self.question.question_text
