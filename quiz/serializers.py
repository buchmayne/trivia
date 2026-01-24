from rest_framework import serializers
from .models import (
    Game,
    Question,
    Answer,
    QuestionRound,
)


class AnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = [
            "id",
            "text",
            "points",
            "answer_text",
            "question_image_url",
            "answer_image_url",
            "question_video_url",
            "answer_video_url",
            "display_order",
            "correct_rank",
        ]


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
            "question_video_url",
            "answer_video_url",
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


class GameDetailSerializer(serializers.ModelSerializer):
    total_questions = serializers.SerializerMethodField()

    class Meta:
        model = Game
        fields = ["id", "name", "description", "total_questions"]

    def get_total_questions(self, obj):
        return obj.questions.count()


class AnswerForGameSerializer(serializers.ModelSerializer):
    """Complete answer information for game display"""

    class Meta:
        model = Answer
        fields = [
            "id",
            "text",
            "points",
            "answer_text",
            "question_image_url",
            "answer_image_url",
            "question_video_url",
            "answer_video_url",
            "display_order",
            "correct_rank",
        ]


class QuestionWithAnswersSerializer(serializers.ModelSerializer):
    answers = AnswerForGameSerializer(many=True, read_only=True)
    question_type = serializers.CharField(
        source="question_type.name", read_only=True
    )  # Get the name instead of ID

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
            "question_video_url",
            "answer_video_url",
            "answers",
        ]
