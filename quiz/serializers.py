from rest_framework import serializers
from .models import Game, Question, Answer, QuestionRound


class AnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = ["id", "text", "points", "answer_text", "explanation", "question_image_url", "answer_image_url", "display_order", "correct_rank"]


class QuestionSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            "id",
            "text",
            "question_type",
            "question_number",
            "total_points",
            "question_image_url",
            "answer_image_url",
            "answers",
        ]


class GameRoundSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionRound
        fields = ["id", "name", "round_number", "description"]


class GameSerializer(serializers.ModelSerializer):
    rounds = GameRoundSerializer(source="questionround_set", many=True, read_only=True)

    class Meta:
        model = Game
        fields = ["id", "name", "description", "created_at", "rounds"]
