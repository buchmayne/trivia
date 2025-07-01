from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
import random
import string
from .models import Game, Question, GameSession, SessionTeam, TeamAnswer
from .serializers import (
    GameDetailSerializer, 
    QuestionWithAnswersSerializer,
    SessionCreateSerializer,
    TeamAnswerSubmissionSerializer
)

@api_view(['POST'])
@permission_classes([AllowAny])
def create_session(request):
    """Go service calls this to create new session"""
    serializer = SessionCreateSerializer(data=request.data)
    if serializer.is_valid():
        session = serializer.save(
            session_code=''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        )
        return Response({
            'session_id': session.id,
            'session_code': session.session_code,
            'game_id': session.game.id,
            'game_name': session.game.name,
            'max_teams': session.max_teams
        })
    return Response(serializer.errors, status=400)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_game_questions(request, game_id):
    """Go service fetches all questions for a game"""
    game = get_object_or_404(Game, id=game_id)
    questions = game.questions.all().order_by('question_number')
    serializer = QuestionWithAnswersSerializer(questions, many=True)
    return Response({
        'game': GameDetailSerializer(game).data,
        'questions': serializer.data
    })

@api_view(['POST'])
# @permission_classes([AllowAny])
def submit_team_answer(request):
    """Go service submits answers for scoring"""
    serializer = TeamAnswerSubmissionSerializer(data=request.data)
    if serializer.is_valid():
        answer = serializer.save()
        return Response({
            'status': 'saved', 
            'answer_id': answer.id,
            'points_awarded': answer.points_awarded
        })
    return Response(serializer.errors, status=400)

@api_view(['POST'])
# @permission_classes([AllowAny])
def update_session_status(request, session_id):
    """Go service updates session status and current question"""
    session = get_object_or_404(GameSession, id=session_id)
    
    new_status = request.data.get('status')
    if new_status:
        session.status = new_status
        if new_status == 'active' and not session.started_at:
            session.started_at = timezone.now()
        elif new_status == 'completed' and not session.completed_at:
            session.completed_at = timezone.now()
    
    current_question = request.data.get('current_question_number')
    if current_question is not None:
        session.current_question_number = current_question
    
    session.save()
    return Response({'status': 'updated'})

@api_view(['POST'])
# @permission_classes([AllowAny])
def add_team_to_session(request, session_id):
    """Go service adds team to session"""
    session = get_object_or_404(GameSession, id=session_id)
    team_name = request.data.get('team_name')
    
    if not team_name:
        return Response({'error': 'team_name required'}, status=400)
    
    # Check if team name already exists in this session
    if session.teams.filter(team_name=team_name).exists():
        return Response({'error': 'Team name already taken'}, status=400)
    
    # Check if session is full
    if session.teams.count() >= session.max_teams:
        return Response({'error': 'Session is full'}, status=400)
    
    team = SessionTeam.objects.create(
        session=session,
        team_name=team_name
    )
    
    return Response({
        'team_id': team.id,
        'team_name': team.team_name,
        'joined_at': team.joined_at
    })

@api_view(['POST'])
# @permission_classes([AllowAny])
def finalize_session(request, session_id):
    """Go service marks session complete, sends final results"""
    session = get_object_or_404(GameSession, id=session_id)
    session.status = 'completed'
    session.completed_at = timezone.now()
    session.save()
    
    # Update final team scores
    teams_data = request.data.get('teams', [])
    for team_data in teams_data:
        SessionTeam.objects.filter(
            session=session, 
            team_name=team_data['name']
        ).update(total_score=team_data['score'])
    
    return Response({'status': 'session_finalized'})

@api_view(['GET'])
# @permission_classes([AllowAny])
def get_session_info(request, session_id):
    """Go service gets current session state"""
    session = get_object_or_404(GameSession, id=session_id)
    teams = session.teams.all()
    
    return Response({
        'session_id': session.id,
        'session_code': session.session_code,
        'status': session.status,
        'current_question_number': session.current_question_number,
        'game_id': session.game.id,
        'game_name': session.game.name,
        'host_name': session.host_name,
        'teams': [
            {
                'id': team.id,
                'name': team.team_name,
                'score': team.total_score,
                'is_connected': team.is_connected
            } for team in teams
        ]
    })