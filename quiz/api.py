from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Game, Question, QuestionRound
from .serializers import (
    GameDetailSerializer,
    QuestionWithAnswersSerializer,
    GameSerializer,
    QuestionSerializer,
    GameRoundSerializer,
)
from django_filters.rest_framework import DjangoFilterBackend


class GameViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Game.objects.all()
    serializer_class = GameSerializer

    @action(detail=True)
    def questions(self, request, pk=None):
        """Get all questions for a specific game"""
        questions = Question.objects.filter(game_id=pk).order_by("question_number")
        serializer = QuestionSerializer(questions, many=True)
        return Response(serializer.data)

    @action(detail=True)
    def rounds(self, request, pk=None):
        """Get all rounds for a specific game"""
        rounds = (
            QuestionRound.objects.filter(questions__game_id=pk)
            .distinct()
            .order_by("round_number")
        )
        serializer = GameRoundSerializer(rounds, many=True)
        return Response(serializer.data)


class QuestionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        "game__name": ["exact"],
        "game__id": ["exact"],
        "question_number": ["exact"],
        "game_round__name": ["exact"],
        "game_round__id": ["exact"],
        "category__name": ["exact"],
    }
