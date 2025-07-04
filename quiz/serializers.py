from rest_framework import serializers
from .models import Game, Question, Answer, GameSession, SessionTeam, TeamAnswer, QuestionRound


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
        fields = ['id', 'name', 'description', 'total_questions']
    
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
    question_type = serializers.CharField(source='question_type.name', read_only=True)  # Get the name instead of ID
    
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

class SessionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameSession
        fields = ['game', 'host_name']  # Removed 'max_teams'

class SessionTeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionTeam
        fields = ['id', 'team_name', 'total_score', 'is_connected', 'joined_at']

class GameSessionSerializer(serializers.ModelSerializer):
    teams = SessionTeamSerializer(many=True, read_only=True)
    game_name = serializers.CharField(source='game.name', read_only=True)
    
    class Meta:
        model = GameSession
        fields = [
            'id', 
            'session_code', 
            'game', 
            'game_name',
            'host_name', 
            'status', 
            'current_question_number',
            'max_teams',
            'created_at',
            'started_at',
            'completed_at',
            'teams'
        ]

class TeamAnswerSubmissionSerializer(serializers.ModelSerializer):
    team_id = serializers.IntegerField(source='team.id')
    question_id = serializers.IntegerField(source='question.id')
    
    class Meta:
        model = TeamAnswer
        fields = ['team_id', 'question_id', 'submitted_answer', 'points_awarded']
    
    def create(self, validated_data):
        team_data = validated_data.pop('team')
        question_data = validated_data.pop('question')
        
        team = SessionTeam.objects.get(id=team_data['id'])
        question = Question.objects.get(id=question_data['id'])
        
        return TeamAnswer.objects.create(
            team=team,
            question=question,
            **validated_data
        )